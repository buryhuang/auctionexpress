# coding: gbk
#----------------------------------------------------------------------------
# Name:         TextEditor.py
# Purpose:      Text Editor for pydocview
#
# Author:       Peter Yared
#
# Created:      8/15/03
# CVS-ID:       $Id: TextEditor.py 46336 2007-06-05 21:50:57Z RD $
# Copyright:    (c) 2003-2005 ActiveGrid, Inc.
# License:      wxWindows License
#----------------------------------------------------------------------------
import wx
import wx.html
#import wx.lib.iewin
import wx.lib.docview
import wx.lib.pydocview
import string
import threading
from zope.testbrowser.browser import Browser
import re
import ClientForm
import datetime
import time

#Customized Classes
import Utilities
from Utilities import LoginIntoTaobao
from Utilities import GlobalConfigParm
from Utilities import WebBitmap
from Utilities import TaobaoBrowser
from Utilities import TaobaoWorkerEvent
from Utilities import GetAddressMap
from Utilities import TaskData
from Utilities import DebugLog

from AccountInfoUI import AccountInfoPanel
from TaskDetailUI import TaskDetailDialog
_ = wx.GetTranslation

class TextDocument(wx.lib.docview.Document):
    
    def __init__(self):
        wx.lib.docview.Document .__init__(self)
        self._inModify = False
        self._data = None

    def SaveObject(self, fileObject):
        view = self.GetFirstView()
        val = view.GetTextCtrl().GetValue()
        if wx.USE_UNICODE:
            val = val.encode('utf-8')
        fileObject.write(val)
        return True


    def LoadObject(self, fileObject):
        view = self.GetFirstView()
        data = fileObject.read()
        if wx.USE_UNICODE:
            data = data.decode('utf-8')
        view.GetTextCtrl().SetValue(data)
        return True


    def IsModified(self):
        view = self.GetFirstView()
        if view and view.GetTextCtrl():
            #return view.GetTextCtrl().IsModified()
            return False
        return False


    def Modify(self, modify):
        if self._inModify:
            return
        self._inModify = True
        
        view = self.GetFirstView()
        #if not modify and view and view.GetTextCtrl():
            #view.GetTextCtrl().DiscardEdits()
        wx.lib.docview.Document.Modify(self, modify)  # this must called be after the DiscardEdits call above.
        self._inModify = False

class TextView(wx.lib.docview.View):

    class remainTimeTimer (wx.Timer):
        def __init__(self, startTime,staticCtrl,startAheadInMs,actionTaker):
            wx.Timer.__init__(self)
            self._startTime = startTime
            self._static = staticCtrl
            self._startAheadInMs = startAheadInMs
            self._actionTaker = actionTaker
            self._auctionFinished = False
            
        def Notify(self):
            now = datetime.datetime.now()
            #print str(self._startTime - now)
            td = self._startTime - now
            if self._static:
                self._static.SetLabel(str(td))
            if not self._auctionFinished and self._actionTaker._startAuction:
                if td < datetime.timedelta(milliseconds=self._startAheadInMs):
                    self._actionTaker.StartAuction(None)
                    self._auctionFinished = True
            if self._startTime < now:
                self.Stop()

    class auctionTimeTimer (wx.Timer):
        def __init__(self, actionTaker):
            wx.Timer.__init__(self)
            self._actionTaker = actionTaker
            self._auctionInterval = 0
            self._auctionIntervalCountdown = 0
            self._index = 0
            self._mode = 0
            self._oldstate = -1
            self._isFirst = True
            self._quantity = 1
        
        def SetAuctionParm(self, startindex, interval, mode, quantity=1):
            self._auctionInterval = interval
            self._auctionIntervalCountdown = -1
            self._mode = mode
            self._index = startindex-1
            self._quantity = string.atoi(quantity)
        
        def Notify(self):
            actionTaker = self._actionTaker
            if self._mode == 0:#孤品模式
                #self._index is next potential worker's index
                #each timer hit and interval countdown arrives, kick off the worker
                #and set the self_index to next worker
                if self._auctionIntervalCountdown <= 0:
                    self._auctionIntervalCountdown = self._auctionInterval
                    index = 0
                    for index in range(self._index,len(actionTaker._workerStates)):
                        if actionTaker._workerStates[index] == actionTaker.STATE_WAITFORBID:
                            self._index = index+1
                            #print DebugLog('worker %d ready for bid' % (index))
                            actionTaker.PreStateChange(index)
                            oldstate = actionTaker._workerStates[index]
                            actionTaker._workerThreadEventSignals[index]=TaobaoWorkerEvent.EVT_DO_BID
                            actionTaker._workerThreadEvents[index].set()
                            break
                    #The loop ends when index==(workerNum-1)
                    if index >= (len(actionTaker._workerStates)-1):
                        self.Stop()
                self._auctionIntervalCountdown -= GlobalConfigParm.AUCTION_TIMER_INTERVAL
                #print '%d - %d'%(self._index,self._auctionIntervalCountdown)
            elif self._mode == 1:#普通模式
                #logic is:
                #self._index is the current running worker
                #on each timer hit, check current running worker's state
                #if the state is changed, self._index move to next potential worker's index
                state = 0
                if not self._isFirst:
                    state = actionTaker._workerStates[self._index]
                else:
                    state = 0
                    self._isFirst = False
                #print 'idx %d - old: %d vs cur %d'%(self._index,self._oldstate,state)
                if state == TextView.STATE_BIDDONE:
                    self._quantity -= 1
                #print "quantity left: %d"%(self._quantity)
                if state != self._oldstate and self._quantity>0:
                    #find next available only
                    #here means the worker is done. ie state changed
                    self._oldstate = state
                    index = 0
                    import time
                    time.sleep(float(self._auctionInterval)/1000)

                    #if self._index is already workerNum-1, +1 will hit outbound
                    if (self._index+1)<len(actionTaker._workerStates):
                        for index in range(self._index+1,len(actionTaker._workerStates)):
                            if actionTaker._workerStates[index] == actionTaker.STATE_WAITFORBID:
                                self._index = index
                                self._oldstate = actionTaker._workerStates[index] 
                                #print DebugLog('worker %d ready for bid' % (index))
                                actionTaker.PreStateChange(index)
                                oldstate = actionTaker._workerStates[index]
                                actionTaker._workerThreadEventSignals[index]=TaobaoWorkerEvent.EVT_DO_BID
                                actionTaker._workerThreadEvents[index].set()
                                break
                        else:
                            #all worker iterated
                            self.Stop()
                elif self._quantity<=0:
                    #quantity met, stop
                    self.Stop()

    #----------------------------------------------------------------------------
    # Overridden methods
    #----------------------------------------------------------------------------

    STATE_NOTSTARTED = 1
    STATE_WAITFORCHECKCODE = 2
    STATE_WAITFORBID = 3
    STATE_BIDDONE = 4
    STATE_BIDFAILED = 5
    StateStr = {
        STATE_NOTSTARTED:'NotSted',
        STATE_WAITFORCHECKCODE:'WtForCC',
        STATE_WAITFORBID:'WtForBid',
        STATE_BIDDONE:'BidDone',
        STATE_BIDFAILED:'BifFail'
    }
    
    PAGE_DETAIL = 1
    PAGE_CHECKCODE_ADDR = 2
    PAGE_PAY = 3
    PAGE_NOT_STARTED = 4
    PAGE_FINISHED = 5
    PAGE_OTHER = 6
    PageStr = {
        PAGE_DETAIL:'Detail',
        PAGE_CHECKCODE_ADDR:'CCADDR',
        PAGE_PAY:'PAY',
        PAGE_NOT_STARTED:'NotSted',
        PAGE_FINISHED:'Fnshed',
        PAGE_OTHER:'Other'
    }

    
    def __init__(self):
        wx.lib.docview.View.__init__(self)
        self._textCtrl = None
        self._listCtrl = None
        self._clockPanel = None
        self._clockText = None
        self._wordWrap = wx.ConfigBase_Get().ReadInt("TextEditorWordWrap", True)
        self._statusString = '尚未开始'
        self._statusTextCtrls = []
        self._statusPanels = []
        self._actionListCtrls = []
        self._actionButtons = []
        self._checkCodeImageCtrls = []
        self._checkCodeTextCtrls = []
        self._workerLogListCtrls = []
        max_worker_num = GlobalConfigParm.MAX_WORKER_NUM
        self._statusNotes = ['']*max_worker_num
        self._workerThreadList = [None]*max_worker_num
        self._workerThreadEvents = [None]*max_worker_num
        self._workerThreadIdleEvent = threading.Event()
        self._workerThreadEventSignals = [None]*max_worker_num
        self._workerStates = [self.STATE_NOTSTARTED]*max_worker_num
        self._frame = None
        
        self._startTimeAheadInMs = 2000 #ms = /1000 second
        self._auctionIntervalForSingle = self._startTimeAheadInMs/GlobalConfigParm.MAX_WORKER_NUM #孤品
        self._auctionIntervalForMultiple = 20 #非孤品
        
        self._startAuction = False
        
        self._auctionTimer = self.auctionTimeTimer(self)
        
    def OnEditDetail(self,event):
        taskDetailDialog = TaskDetailDialog(self._frame,self.GetDocument()._data)
        newAnswer = taskDetailDialog.ShowModal()
        if newAnswer == wx.ID_OK :
            self.ProcessEvent(event)
            self.GetDocumentManager().GetCurrentDocument()._data=taskDetailDialog._data
            self.GetDocumentManager().GetCurrentView().InitData()        

    def OnCreate(self, doc, flags):
        self._frame = wx.GetApp().CreateDocumentFrame(self, doc, flags)
        frame = self._frame
        
        self._sizer = wx.FlexGridSizer(cols=1, vgap=5, hgap=5)
        font, color = self._GetFontAndColorFromConfig()

        self._clockPanel = self._BuildClockPanel(frame, font, color = color,value=_("19:00:00 .0000"))
        self._listCtrl = self._BuildListCtrl(frame, font, color = color)
        self._editDetailButton = wx.Button(frame,-1,_('修改信息'))
        self._editDetailButton.Bind(wx.EVT_BUTTON,self.OnEditDetail)
        self._itemImageCtrl = WebBitmap(frame,-1,size=wx.Size(100,50))

        #self._listCtrl.InsertStringItem(0,self.GetDocument().GetData()._itemName)

        upperSizer = wx.FlexGridSizer(cols=4, vgap=5, hgap=5)
        upperSizer.AddGrowableCol(0)
        upperSizer.Add(self._listCtrl, 0, wx.ALIGN_CENTER_VERTICAL|wx.EXPAND)
        upperSizer.Add(self._editDetailButton, 0, wx.ALIGN_CENTER_VERTICAL|wx.EXPAND)
        upperSizer.Add(self._clockPanel, 0, wx.ALIGN_CENTER_VERTICAL)
        upperSizer.Add(self._itemImageCtrl, 0, wx.ALIGN_RIGHT|wx.ALIGN_CENTER_VERTICAL)
        
        #self._textCtrl = self._BuildTextCtrl(frame, font, color = color)
        #self._textCtrl.Bind(wx.EVT_TEXT, self.OnModify)
        self._readyToGoPanel = self._BuildReadyToGoPanel(frame,font,color=color)
        
        self._runningPanel = self._BuildRunningPanel(frame,font,color=color)
        self._runningPanel.Show(False)
        
        #self._listCtrl.Bind(wx.EVT_LIST, self.OnModify)
        
        self._sizer.AddGrowableCol(0)
        self._sizer.AddGrowableRow(1)
        
        self._sizer.Add(upperSizer,wx.EXPAND)
        #sizer.Add(self._BuildListCtrl(frame, font, color = color), 0, wx.ALIGN_CENTER_VERTICAL|wx.EXPAND)
        self._sizer.Add(self._readyToGoPanel, 1, wx.EXPAND, 1)
        
        frame.SetSizer(self._sizer)
        frame.Layout()
        frame.Show(True)
        self.Activate()
        
        return True

    def OnModify(self, event):
        self.GetDocument().Modify(True)
    
    def PreStateChange(self,index):
        self._actionListCtrls[index].Enable(False)
        self._actionButtons[index].Enable(False)

    def AppendLog(self,index,logstr):
        ctrl = self._workerLogListCtrls[index]
        ctrl.Append(DebugLog(logstr))
        ctrl.SetSelection(ctrl.GetCount()-1)
        
    def SetState(self,index,state,notes=''):
        self._workerStates[index]=state
        self._actionListCtrls[index].Enable(True)
        self._actionButtons[index].Enable(True)
        self._statusNotes[index]=notes
        self.AppendLog(index,'Into state%s-%s'%(self.StateStr[state],notes))
        
    def CheckPageState(self,index,browser):
        page = self.PAGE_OTHER
        try:
            if browser.contents.find('doAlipayPay') > 0:
                page=self.PAGE_PAY
            elif browser.contents.find('J_LinkBuy') > 0:
                page=self.PAGE_DETAIL
            elif browser.contents.find('_fma.b._0.di') > 0:
                page=self.PAGE_CHECKCODE_ADDR
        except:
            pass
        self.AppendLog(index,'Page:%s'%self.PageStr[page])
        return page
    
    def TaobaoWorkerDone(self,itemIndex):
        #self._workerThreadEventSignals[itemIndex]=TaobaoWorkerEvent.EVT_QUIT
        #self._workerThreadEvents[itemIndex].set()
        pass
        
    def TaobaoWorker(self, itemUrl, itemIndex, workerEvent):
        browser=TaobaoBrowser()
        while True:
            #hang until events arrive
            workerEvent.wait()
            workerEvent.clear()
            self.PreStateChange(itemIndex)
            signal = self._workerThreadEventSignals[itemIndex]
            self.AppendLog(itemIndex,'GetSgl:%s'%Utilities.TaobaoWorkerEvent.EventStr[signal])
            
            #actions performed below
            if signal == TaobaoWorkerEvent.EVT_GET_CHECKCODE:
                page = self.CheckPageState(itemIndex,browser)
                if page != self.PAGE_CHECKCODE_ADDR:
                    #print self.GetDocument()._data._skuId
                    try:
                        #print self.GetDocument()._data._skuId
                        #print self.GetDocument()._data._skuInfo
                        browser.open(itemUrl)
                        form=browser.getForm('J_FrmBid')
                        if self.GetDocument()._data._skuId is not None:
                            form.getControl(name='skuId').value = self.GetDocument()._data._skuId
                            form.getControl(name='skuInfo').value = self.GetDocument()._data._skuInfo
                        form.submit()
                        #print browser.contents
                        LoginIntoTaobao(browser,self.GetDocument()._data._account,self.GetDocument()._data._password)
                    except:
                        pass
                
                page = self.CheckPageState(itemIndex,browser)
                if page != self.PAGE_CHECKCODE_ADDR:
                    try:
                        #ori1: http://item.taobao.com/auction/item_detail.jhtml?item_id=db4847385a02610789d38c5c85db3175&x_id=0db1
                        #ori2: http://item.taobao.com/auction/item_detail-db1-00ba443804adf140bfe37d1c39606159.jhtml
                        #tgt: http://buy.taobao.com/auction/buy_now.htm?auction_id=414b43f7a76eddf4c0f1522cc99a7d83&x_id=db1
                        p=re.compile('item_id=(.*?)&x_id=(.*)')
                        r = p.findall(itemUrl)
                        if len(r)>0:
                            newurl = 'http://buy.taobao.com/auction/buy_now.htm?auction_id=%s&x_id=%s' % (r[0][0],r[0][1])
                            print newurl
                            browser.open(newurl)
                        else:
                            p=re.compile('item_detail-(.*?)-(.*)\..*?htm')
                            r = p.findall(itemUrl)
                            if len(r)>0:
                                newurl = 'http://buy.taobao.com/auction/buy_now.htm?auction_id=%s&x_id=%s' % (r[0][1],r[0][0])
                                print newurl
                                browser.open(newurl)
                            else:
                                #wx.MessageBox('无法获取验证码,请确认账号,密码等信息是否正确')
                                self.SetState(itemIndex,self.STATE_BIDFAILED,'无法获取验证码')
                                continue
                        #print browser.contents
                        LoginIntoTaobao(browser,self.GetDocument()._data._account,self.GetDocument()._data._password)
                    except:
                        pass
                
                page = self.CheckPageState(itemIndex,browser)
                if page == self.PAGE_CHECKCODE_ADDR:
                    #print browser.contents
                    p= re.compile('src=\"(http:\/\/checkcode.*?)\"')
                    checkCodeUrl = p.findall(browser.contents)
                    if len(checkCodeUrl)>0:
                        #the taobao reload checkcode need this, so i copied it
                        import time
                        checkCodeUrl[0]+= '&t='+str(int(time.time()))
                        #print str(checkCodeUrl[0])
                
                        self._checkCodeImageCtrls[itemIndex].Load(str(checkCodeUrl[0]))
                        self._checkCodeImageCtrls[itemIndex].Show(True)
                        self._checkCodeTextCtrls[itemIndex].SetValue('')
                        self._checkCodeTextCtrls[itemIndex].Enable(True)
                        
                        self.SetState(itemIndex,self.STATE_WAITFORCHECKCODE)
                    else:
                        #wx.MessageBox('无法获取验证码,请确认账号,密码等信息是否正确')
                        self.SetState(itemIndex,self.STATE_BIDFAILED,'无法获取验证码')
                else:
                    #wx.MessageBox('无法获取验证码,请确认账号,密码等信息是否正确')
                    self.SetState(itemIndex,self.STATE_BIDFAILED,'无法获取验证码页面')
            elif signal == TaobaoWorkerEvent.EVT_DO_BID:
                #print browser.contents
                #for i in browser.mech_browser.forms():
                #    print i
                form=browser.getForm(id='mainform')

                #select Address
                addrMap = GetAddressMap()
                addrIndex = self.GetDocument()._data._addrIndex
                #print addrMap[self.GetDocument()._data._account][addrIndex]
                addrName = unicode(addrMap[self.GetDocument()._data._account][addrIndex]['AddressName'])
                addrArea = unicode(addrMap[self.GetDocument()._data._account][addrIndex]['AddressArea'])#广东省 珠海市 斗门区
                addrFull = unicode(addrMap[self.GetDocument()._data._account][addrIndex]['AddressFull'])
                addrPost = unicode(addrMap[self.GetDocument()._data._account][addrIndex]['AddressPost'])
                addrPhone = unicode(addrMap[self.GetDocument()._data._account][addrIndex]['AddressPhone']) #0756-6880026 <br />13750065111
                addrId = unicode('add'+str(addrMap[self.GetDocument()._data._account][addrIndex]['AddressId']))
                addrList = form.getControl(name='address')
                #for a in addrList.displayOptions:
                #    print a
                addrLabel = addrName+' '+addrArea+addrFull
                #print addrLabel
                #addrList.getControl(addrLabel.encode('gbk')).selected=True
                #need to set hidden fields
                #TODO: calculate addr code according to address!
                #this can be done by duplicating disctselector.js

                #pretty kludge..well, adding an option to a null select
                #doesn't work as easy as it looks
                #provSelect = form.mech_form.find_control('n_prov')
                #del form.mech_form.controls[form.mech_form.controls.index(provSelect)]
                #form.mech_form.new_control('text','n_prov',{'value':'440000'})

                #citySelect = form.mech_form.find_control(name='n_city')
                #del form.mech_form.controls[form.mech_form.controls.index(citySelect)]
                #form.mech_form.new_control('text','n_city',{'value':'440400'})
                
                #areaSelect = form.mech_form.find_control(name='n_area')
                #del form.mech_form.controls[form.mech_form.controls.index(areaSelect)]
                #form.mech_form.new_control('text','n_area',{'value':'440403'})
                
                form.getControl(name='_fma.b._0.di').value=Utilities.LocateAreaCode(addrArea)
                form.getControl(name='_fma.b._0.po').value=addrPost.encode('gbk')#邮编
                form.getControl(name='_fma.b._0.d').value=addrFull.encode('gbk')#地址
                form.getControl(name='_fma.b._0.de').value=addrName.encode('gbk')#收货人姓名
                #0756-6880026 <br />13750065111
                p=re.compile('([\d-]*).*?br.*?(\d+)')
                r1 = p.findall(addrPhone) # r1=[('0756-6880026', '13750065111')]
                if len(r1)>0:
                    try:
                        form.getControl(name='_fma.b._0.deli').value=r1[0][1]
                    except:
                        pass
                    try:
                        r2 = r1[0][0].split('-')# r2 = ['0756', '6880026']
                        try:
                            form.getControl(name='_fma.b._0.ph').value=r2[0]#区号
                        except:
                            pass
                        try:
                            form.getControl(name='_fma.b._0.pho').value=r2[1]#电话号码
                        except:
                            pass
                        try:
                            form.getControl(name='_fma.b._0.phon').value=r2[2]#分机
                        except:
                            pass
                    except:
                        pass
                
                #set request quantity
                
                #set anonymous
                form.getControl(name='anony').controls[0].selected = True
                
                #set checkcode
                #print self._checkCodeTextCtrls[itemIndex].GetValue()
                form.getControl(name='_fma.b._0.c').value=self._checkCodeTextCtrls[itemIndex].GetValue().encode('gbk')
                
                #set comment to null
                form.getControl(name='_fma.b._0.w').value=''
                
                #submit and go
                #for i in browser.mech_browser.forms():
                #    print i
                
                form.submit()
                
                #print browser.contents
                #print "biddone"
                page = self.CheckPageState(itemIndex,browser)
                if page == self.PAGE_PAY:
                    self.SetState(itemIndex,self.STATE_BIDDONE)
                elif page == self.PAGE_CHECKCODE_ADDR:
                    self.SetState(itemIndex,self.STATE_BIDFAILED)
                    notes = ''
                    if browser.contents.find('抱歉，此宝贝还没有开始出售'):
                        notes = '还没有开始出售'
                    #self.PreStateChange(itemIndex)
                    #self._workerThreadEventSignals[itemIndex]=TaobaoWorkerEvent.EVT_GET_CHECKCODE
                    #self._workerThreadEvents[itemIndex].set()
                    #self.SetState(itemIndex,self.STATE_WAITFORCHECKCODE)
                else:
                    self.SetState(itemIndex,self.STATE_BIDFAILED)

            elif signal == TaobaoWorkerEvent.EVT_QUIT:
                #print 'quiting'
                self._checkCodeTextCtrls[itemIndex].SetValue('')
                self._checkCodeTextCtrls[itemIndex].Enable(False)
                self._checkCodeImageCtrls[itemIndex].Show(False)
                self.SetState(itemIndex,self.STATE_NOTSTARTED)
                break
            else:
                print DebugLog("Unknow signal received %d"%signal)
            #Notify to proceed to next step
            #Notify the state change
            self.OnStateChanged(itemIndex)
            self._workerThreadIdleEvent.set()
        
        #for quit event, state change need to be handled
        self.OnStateChanged(itemIndex)
        self._workerThreadIdleEvent.set()
        
    def StartTaobaoWorker(self, index) :
        workerEvent=threading.Event()
        workerEvent.clear()

        threadWorker = threading.Thread(
            target=self.TaobaoWorker,
            args=[
                self.GetDocument()._data._itemUrl,
                index,
                workerEvent
                ]
            )
        self._workerThreadList[index]=threadWorker
        threadWorker.start()
        self._workerThreadEvents[index]=workerEvent

        #the first event is EVT_GET_CHECKCODE
        self._workerThreadEventSignals[index]=TaobaoWorkerEvent.EVT_GET_CHECKCODE
        workerEvent.set()

    def CloseAllWorker(self):
        #clear all controls first
        for c in self._checkCodeTextCtrls:
            c.Enable(False)
        for c in self._checkCodeImageCtrls:
            c.Show(False)
        #close all thread by sending EVT_QUIT
        for i in range(0,GlobalConfigParm.MAX_WORKER_NUM):
            if self._workerThreadEvents[i]:
                self._workerThreadEventSignals[i]=TaobaoWorkerEvent.EVT_QUIT
                self._workerThreadEvents[i].set()
        
    def OnOpenWorkers(self, event) :
        if unicode(self._getCheckCodeButton.GetLabel())==unicode('开启淘宝工人'.decode('gbk')):
            try:
                workerNum = string.atoi(self._workerNumberTextCtrl.GetValue())
            except:
                wx.MessageBox('辅助拍卖数目不正确')
                return
    
            #print workerNum
            if workerNum > 0:
                self._workerNumberTextCtrl.Enable(False)
                self._getCheckCodeButton.SetLabel('关闭所有工人')
                for c in self._checkCodeTextCtrls:
                    c.Enable(False)
                for c in self._checkCodeImageCtrls:
                    c.Show(False)
                for i in range(0,workerNum):
                    self.StartTaobaoWorker(i)
            else:
                wx.MessageBox('辅助拍卖数目不正确')
        else:
            self.CloseAllWorker()
            self._workerNumberTextCtrl.Enable(True)
            self._getCheckCodeButton.SetLabel('开启淘宝工人')


    def GetActionHandler(self,index):
        def OnAction(event):
            curState = self._workerStates[index]
            self._statusPanels[index].SetBackgroundColour(wx.LIGHT_GREY)
            self._statusPanels[index].Hide()
            self._statusPanels[index].Show()
            #print 'item %d curState is %d' % (int(index),int(curState))
            
            #perform action, state may change here
            action = self._actionListCtrls[index].GetSelection()
            curState = self._workerStates[index]
            if curState == self.STATE_NOTSTARTED:
                if action == 0: #开启本工人
                    self.StartTaobaoWorker(index)
            elif curState == self.STATE_WAITFORCHECKCODE:
                if action == 0: #验证码输入完毕
                    self.PreStateChange(index)
                    if len(self._checkCodeTextCtrls[index].GetValue())==0:
                        wx.MessageBox('请输入验证码')
                        self.SetState(index,self.STATE_WAITFORCHECKCODE)
                    else:
                        self._checkCodeTextCtrls[index].Enable(False)
                        self.SetState(index,self.STATE_WAITFORBID)
                elif action == 1: #更换验证码
                    self.PreStateChange(index)
                    self._workerThreadEventSignals[index]=TaobaoWorkerEvent.EVT_GET_CHECKCODE
                    self._workerThreadEvents[index].set()
                elif action == 2: #关闭此工人
                    self.PreStateChange(index)
                    self._workerThreadEventSignals[index]=TaobaoWorkerEvent.EVT_QUIT
                    self._workerThreadEvents[index].set()
            elif curState == self.STATE_WAITFORBID:
                if action == 0: #开始拍卖!
                    self.PreStateChange(index)
                    self._workerThreadEventSignals[index]=TaobaoWorkerEvent.EVT_DO_BID
                    self._workerThreadEvents[index].set()
                elif action == 1: #关闭此工人
                    self.PreStateChange(index)
                    self._workerThreadEventSignals[index]=TaobaoWorkerEvent.EVT_QUIT
                    self._workerThreadEvents[index].set()
            elif curState == self.STATE_BIDDONE or curState == self.STATE_BIDFAILED:
                if action == 0:
                    self.PreStateChange(index)
                    self._workerThreadEventSignals[index]=TaobaoWorkerEvent.EVT_QUIT
                    self._workerThreadEvents[index].set()
            self.OnStateChanged(index)

            for i in range(index,GlobalConfigParm.MAX_WORKER_NUM):
                if self._workerStates[i] == self.STATE_WAITFORCHECKCODE:
                    self._checkCodeTextCtrls[i].SetFocus()
                    break
            
        return OnAction

    def OnStateChanged(self,index):
        curState = self._workerStates[index]
        #print 'item %d curState is %d' % (int(index),int(curState))

        #change label & color according to state
        curState = self._workerStates[index]
        if curState == self.STATE_NOTSTARTED:
            self._statusTextCtrls[index].SetLabel(_("运行状态: 工人尚未开启"))
            self._statusPanels[index].SetBackgroundColour(wx.LIGHT_GREY)
            self._statusPanels[index].Hide()
            self._statusPanels[index].Show()
        elif curState == self.STATE_WAITFORCHECKCODE:
            label = '运行状态: 等待输入验证码[%s]' % self._statusNotes[index]
            self._statusTextCtrls[index].SetLabel(_(label))
            self._statusPanels[index].SetBackgroundColour(wx.Colour(255,165,0))
            self._statusPanels[index].Hide()
            self._statusPanels[index].Show()
        elif curState == self.STATE_WAITFORBID:
            self._statusTextCtrls[index].SetLabel(_("运行状态: 等待发起拍卖"))
            self._statusPanels[index].SetBackgroundColour(wx.Colour(255,165,0))
            self._statusPanels[index].Hide()
            self._statusPanels[index].Show()
        elif curState == self.STATE_BIDDONE:
            self._statusTextCtrls[index].SetLabel(_("运行状态: 抢拍成功!"))
            self._statusPanels[index].SetBackgroundColour(wx.GREEN)
            self._statusPanels[index].Hide()
            self._statusPanels[index].Show()
        elif curState == self.STATE_BIDFAILED:
            label = '运行状态: 抢拍失败[%s]' % self._statusNotes[index]
            self._statusTextCtrls[index].SetLabel(_(label))
            self._statusPanels[index].SetBackgroundColour(wx.Colour(255,255,0))
            self._statusPanels[index].Hide()
            self._statusPanels[index].Show()
            
        #change the action list according to state
        self._actionListCtrls[index].Clear()
        if curState == self.STATE_NOTSTARTED:
            #self._actionListCtrls[index].Enable(False)
            self._actionListCtrls[index].Append('开启本工人') #index 0
            self._actionListCtrls[index].SetSelection(0)
            pass
        elif curState == self.STATE_WAITFORCHECKCODE:
            self._actionListCtrls[index].Enable(True)
            self._actionListCtrls[index].Append('验证码输入完毕') #index 0
            self._actionListCtrls[index].Append('更换验证码') #index 1
            self._actionListCtrls[index].Append('关闭本工人') #index 2
            self._actionListCtrls[index].SetSelection(0)
        elif curState == self.STATE_WAITFORBID:
            self._actionListCtrls[index].Enable(True)
            self._actionListCtrls[index].Append('发起拍卖!') #index 0
            self._actionListCtrls[index].Append('关闭本工人') #index 1
            self._actionListCtrls[index].SetSelection(0)
        elif curState == self.STATE_BIDDONE or curState == self.STATE_BIDFAILED:
            self._actionListCtrls[index].Enable(True)
            self._actionListCtrls[index].Append('关闭本工人') #index 0
            self._actionListCtrls[index].SetSelection(0)

    
    def OnStartAuction(self,event):
        if self._startButton.GetLabel() == '开始定时抢拍'.decode('gbk'):
            notFound = True
            for index in range(0,len(self._workerStates)):
                if self._workerStates[index] == self.STATE_WAITFORBID:
                    notFound = False
            if notFound:
                wx.MessageBox("没有工人就绪,无法开始抢拍")
                return
            self._startAuction = True
            self._startButton.SetLabel('取消定时抢拍')
            self._auctionAheadInMsTextCtrl.Enable(False)
            self._auctionIntervalInMsTextCtrl.Enable(False)
            self._auctionModeList.Enable(False)
        else:
            self._startAuction = False
            self._startButton.SetLabel('开始定时抢拍')
            self._auctionAheadInMsTextCtrl.Enable(True)
            self._auctionIntervalInMsTextCtrl.Enable(True)
            self._auctionModeList.Enable(True)
    
    def StartAuction(self,event):
        if self._auctionTimer.IsRunning():
            wx.MessageBox('抢拍已经进行中')
            return;

        notFound = True
        
        selection = self._auctionModeList.GetSelection()
        interval = 0
        if selection ==0:#孤品模式
            interval = self._auctionIntervalForSingle
        else:#普通模式
            interval = self._auctionIntervalForMultiple
        
        for index in range(0,len(self._workerStates)):
            if self._workerStates[index] == self.STATE_WAITFORBID:
                notFound = False
        if notFound:
            wx.MessageBox("没有工人就绪,请确认")
        else:
            self._auctionTimer.SetAuctionParm(0,interval,selection,self.GetDocument()._data._quantityRequested)
            self._auctionTimer.Start(GlobalConfigParm.AUCTION_TIMER_INTERVAL)
    
    def OnChangeAuctionMode(self,event):
        selection = self._auctionModeList.GetSelection()
        if  selection == 0: #孤品模式
                self._auctionIntervalInMsTextCtrl.SetValue(str(self._auctionIntervalForSingle))
        else: #普通模式
                self._auctionIntervalInMsTextCtrl.SetValue(str(self._auctionIntervalForMultiple))
        
    def OnChangeAuctionParm(self,event):
        self._workerNumberTextCtrl.Bind(wx.EVT_TEXT,None)
        try:
            n=string.atoi(self._auctionAheadInMsTextCtrl.GetValue())
            self._startTimeAheadInMs = n
        except:
            pass
        selection = self._auctionModeList.GetSelection()
        interval = 0
        if selection == 0:#孤品模式
            try:
                n=string.atoi(self._auctionIntervalInMsTextCtrl.GetValue())
                self._auctionIntervalForSingle = n
                interval = n
                #print str(interval)

                if interval > 0:
                    workerNum = self._startTimeAheadInMs/interval + 2
                    #print str(workerNum)
                    if workerNum > GlobalConfigParm.MAX_WORKER_NUM:
                        workerNum = GlobalConfigParm.MAX_WORKER_NUM
                    self._workerNumberTextCtrl.SetValue(str(workerNum))
            except:
                pass
        else: #非孤品模式
            try:
                n=string.atoi(self._auctionIntervalInMsTextCtrl.GetValue())
                self._auctionIntervalForMultiple = n
                interval = n
            except:
                pass
        self._workerNumberTextCtrl.Bind(wx.EVT_TEXT,self.OnChangeWorkerNumber)

    def OnChangeWorkerNumber(self,event):
        self._auctionIntervalInMsTextCtrl.Bind(wx.EVT_TEXT,None)
        selection = self._auctionModeList.GetSelection()
        if selection == 0:#孤品模式
            try:
                workerNum = string.atoi(self._workerNumberTextCtrl.GetValue())
                if workerNum > 0:
                    self._auctionIntervalInMsTextCtrl.SetValue(str((self._startTimeAheadInMs+300)/workerNum))
            except:
                pass
        self._auctionIntervalInMsTextCtrl.Bind(wx.EVT_TEXT,self.OnChangeAuctionParm)
    
    def _BuildReadyToGoPanel(self, parent, font, color = wx.BLACK, value = "", selection = [0, 0]):
        readyToGoPanel = wx.Panel(parent, -1, pos = wx.DefaultPosition, size = wx.DefaultSize)
        borderSizer = wx.StaticBoxSizer(wx.StaticBox(readyToGoPanel, -1,_('运行状态')),wx.VERTICAL)
        
        baseSizer = wx.FlexGridSizer(cols=1, vgap=5, hgap=5)

        lineSizer1 = wx.BoxSizer(wx.HORIZONTAL)
        workerNumberStaticText = wx.StaticText(readyToGoPanel,-1,"总抢拍工人数量(1-24)")
        self._workerNumberTextCtrl = wx.TextCtrl(readyToGoPanel,-1)
        self._workerNumberTextCtrl.SetValue(str(GlobalConfigParm.MAX_WORKER_NUM))
        self._workerNumberTextCtrl.Bind(wx.EVT_TEXT,self.OnChangeWorkerNumber)
        self._getCheckCodeButton = wx.Button(readyToGoPanel, -1, _("开启淘宝工人"))
        self._getCheckCodeButton.Bind(wx.EVT_BUTTON,self.OnOpenWorkers)
        #closeAllWorkerButton = wx.Button(readyToGoPanel, -1, _("关闭所有工人"))
        #closeAllWorkerButton.Bind(wx.EVT_BUTTON,self.OnCloseAllWorker)
        lineSizer1.Add(workerNumberStaticText)
        lineSizer1.Add(self._workerNumberTextCtrl)
        lineSizer1.Add(self._getCheckCodeButton)
        #lineSizer1.Add(closeAllWorkerButton)

        lineSizer2 = wx.BoxSizer(wx.HORIZONTAL)
        #closeAllWorkerButton.Enable(False)
        auctionAheadInMsLabel = wx.StaticText(readyToGoPanel,-1,'提前开拍时间(1/1000秒):')
        self._auctionAheadInMsTextCtrl = wx.TextCtrl(readyToGoPanel,-1,size=wx.Size(50,-1))
        self._auctionAheadInMsTextCtrl.SetValue(str(self._startTimeAheadInMs))
        self._auctionAheadInMsTextCtrl.Bind(wx.EVT_TEXT, self.OnChangeAuctionParm)
        auctionIntervalInMsLabel = wx.StaticText(readyToGoPanel,-1,'    抢拍间隔时间(1/1000秒):')
        self._auctionIntervalInMsTextCtrl = wx.TextCtrl(readyToGoPanel,-1,size=wx.Size(50,-1))
        self._auctionIntervalInMsTextCtrl.SetValue(str(self._auctionIntervalForSingle))
        self._auctionIntervalInMsTextCtrl.Bind(wx.EVT_TEXT, self.OnChangeAuctionParm)
        auctionModeListLabel = wx.StaticText(readyToGoPanel,-1,'    抢拍模式:')
        self._auctionModeList = wx.Choice(readyToGoPanel,-1)
        self._auctionModeList.Append('孤品模式')
        self._auctionModeList.Append('普通模式')
        self._auctionModeList.SetSelection(0)
        self._auctionModeList.Bind(wx.EVT_CHOICE,self.OnChangeAuctionMode)
        self._startButton = wx.Button(readyToGoPanel, -1, _("开始定时抢拍"))
        self._startButton.Enable(True)
        self._startButton.Bind(wx.EVT_BUTTON,self.OnStartAuction)
        self._startNowButton = wx.Button(readyToGoPanel, -1, _("马上开始"))
        self._startNowButton.Enable(True)
        self._startNowButton.Bind(wx.EVT_BUTTON,self.StartAuction)
        lineSizer2.Add(auctionAheadInMsLabel)
        lineSizer2.Add(self._auctionAheadInMsTextCtrl)
        lineSizer2.Add(auctionIntervalInMsLabel)
        lineSizer2.Add(self._auctionIntervalInMsTextCtrl)
        lineSizer2.Add(auctionModeListLabel)
        lineSizer2.Add(self._auctionModeList)
        lineSizer2.Add(self._startButton)
        lineSizer2.Add(self._startNowButton)

        scrollWindow = wx.ScrolledWindow(readyToGoPanel,size=wx.Size(600,400))
        scrollWindow.SetScrollbars(20, 20, 50, 50)
        
        workerAreaBorderSizer = wx.StaticBoxSizer(wx.StaticBox(scrollWindow,-1),wx.HORIZONTAL)
        #statusStaticText = wx.StaticText(readyToGoPanel,-1)
        #statusStaticText.SetLabel(_('尚未开始'))
        #font = wx.Font(14, wx.DEFAULT, wx.NORMAL, wx.NORMAL)
        #statusStaticText.SetFont(font)
        #statusSizer.Add(statusStaticText,1,wx.EXPAND|wx.ALIGN_CENTER_HORIZONTAL)
        workerCol = GlobalConfigParm.WORKER_COL
        workerRow = GlobalConfigParm.WORKER_ROW
        workerInnerSizer = wx.GridSizer(workerRow,workerCol,10,10)
        for i in range(0,workerRow*workerCol):
            self._workerStates.append(self.STATE_NOTSTARTED)
            
            numStr = "%02d" % (i+1)
            tmpStatic = wx.StaticBox(scrollWindow,-1)
            tmpStatic.SetLabel(_("淘宝工人"+numStr))
            gridCellBaseSizer = wx.StaticBoxSizer(tmpStatic,wx.VERTICAL)
            
            #status Row
            statusPanel = wx.Panel(scrollWindow,-1)
            statusPanel.SetBackgroundColour(wx.LIGHT_GREY)
            statusPanelSizer = wx.BoxSizer()
            statusSizer = wx.StaticBoxSizer(wx.StaticBox(scrollWindow,-1),wx.HORIZONTAL)
            statusText = wx.StaticText(statusPanel,-1,size=wx.Size(200,20))
            statusText.SetLabel(_("运行状态: 工人尚未开启"))
            self._statusTextCtrls.append(statusText)
            self._statusPanels.append(statusPanel)
            statusPanelSizer.Add(statusText)
            statusPanel.SetSizer(statusPanelSizer)
            statusSizer.Add(statusPanel,1,wx.ALIGN_CENTER_HORIZONTAL)
            
            #action Row
            actionSizer = wx.StaticBoxSizer(wx.StaticBox(scrollWindow,-1),wx.HORIZONTAL)
            actionLabel = wx.StaticText(scrollWindow,-1)
            actionList = wx.Choice(scrollWindow,-1)
            actionList.Append(_('开启本工人'))
            actionList.SetSelection(0)
            #actionList.Enable(False)
            actionButton = wx.Button(scrollWindow,-1,_("确定"))
            actionButton.Bind(wx.EVT_BUTTON,self.GetActionHandler(i))
            self._actionListCtrls.append(actionList)
            self._actionButtons.append(actionButton)
            actionSizer.Add(actionLabel,0)
            actionSizer.Add(actionList,1)
            actionSizer.Add(actionButton,0)
            
            #checkcode Row
            checkCodeSizer=wx.StaticBoxSizer(wx.StaticBox(scrollWindow,-1),wx.HORIZONTAL)
            checkCodeImageCtrl = WebBitmap(scrollWindow,-1,size=wx.Size(100,40))
            self._checkCodeImageCtrls.append(checkCodeImageCtrl)
            checkCodeTextCtrl = wx.TextCtrl(scrollWindow,-1)
            checkCodeTextCtrl.Enable(False)
            checkCodeTextCtrl.Bind(wx.EVT_TEXT ,self.GetCheckCodeTextChangeHandler(i))
            self._checkCodeTextCtrls.append(checkCodeTextCtrl)
            checkCodeSizer.Add(checkCodeImageCtrl)
            checkCodeSizer.Add(checkCodeTextCtrl)
            
            workerLogListCtrl = wx.ListBox(scrollWindow,-1,size=wx.Size(210,40),style=wx.HSCROLL|wx.VSCROLL)
            self._workerLogListCtrls.append(workerLogListCtrl)
            
            gridCellBaseSizer.Add(statusSizer)
            gridCellBaseSizer.Add(actionSizer)
            gridCellBaseSizer.Add(checkCodeSizer)
            gridCellBaseSizer.Add(workerLogListCtrl)
            workerInnerSizer.Add(gridCellBaseSizer,0)
        
        workerAreaBorderSizer.Add(workerInnerSizer,1)
        scrollWindow.SetSizer(workerAreaBorderSizer)

        baseSizer.AddGrowableCol(0)
        baseSizer.AddGrowableRow(2)#the main area row
        baseSizer.Add(lineSizer1)
        baseSizer.Add(lineSizer2,0,wx.ALIGN_CENTER_VERTICAL)
        baseSizer.Add(scrollWindow,1,wx.EXPAND)
        
        borderSizer.Add(baseSizer,1,wx.EXPAND|wx.ALIGN_CENTER_HORIZONTAL)
        
        readyToGoPanel.SetSizer(borderSizer)
        
        return readyToGoPanel
    
    def GetCheckCodeTextChangeHandler(self,index):
        def OnCheckCodeTextChanged(event):
            #print str(len(self._checkCodeTextCtrls[index].GetValue()))
            if len(self._checkCodeTextCtrls[index].GetValue()) == 4:
                self._actionButtons[index].SetFocus()
        return OnCheckCodeTextChanged
    
    def _BuildRunningPanel(self, parent, font, color = wx.BLACK, value = "", selection = [0, 0]):
        runningPanel = wx.Panel(parent, -1, pos = wx.DefaultPosition, size = wx.DefaultSize)
        borderBox = wx.StaticBox(runningPanel, -1, pos = wx.DefaultPosition, size = wx.DefaultSize, style = wx.TE_MULTILINE | wx.TE_RICH)
        borderBox.SetLabel(_('运行状态'))
        baseSizer = wx.StaticBoxSizer(borderBox)
        startButton = wx.Button(runningPanel, -1, _("开始抢拍"), size=wx.Size(100,-1))
        baseSizer.Add(startButton,0,wx.ALIGN_CENTER_VERTICAL)
        runningPanel.SetSizer(baseSizer)
        
        return runningPanel

    def _BuildClockPanel(self, parent, font, color = wx.BLACK, value = "", selection = [0, 0]):
        if self._wordWrap:
            wordWrapStyle = wx.TE_WORDWRAP
        else:
            wordWrapStyle = wx.TE_DONTWRAP
        clockPanel = wx.Panel(parent, -1, pos = wx.DefaultPosition, size = wx.Size(170,50), style = wx.TE_MULTILINE | wx.TE_RICH | wordWrapStyle)
        clockBox = wx.StaticBox(clockPanel, -1, pos = wx.DefaultPosition, size = wx.Size(170,50), style = wx.TE_MULTILINE | wx.TE_RICH | wordWrapStyle)
        self._clockText = wx.StaticText(clockPanel, -1, pos = wx.Point(17,23), size = wx.Size(150,20), style = wx.TE_MULTILINE | wx.TE_RICH | wordWrapStyle)
        #_clockText = wx.StaticText(parent, -1)
        clockBox.SetLabel(_('距离开拍时间'))
        self._clockText.SetLabel(value)
        
        clockPanel.SetFont(font)
        clockPanel.SetForegroundColour(color)
        return clockPanel

    def _BuildListCtrl(self, parent, font, color = wx.BLACK, value = "", selection = [0, 0]):
        listCtrl = wx.ListBox(parent, -1, pos = wx.DefaultPosition, size = wx.Size(350,80),style=wx.LB_SINGLE)
        listCtrl.SetFont(font)
        listCtrl.SetForegroundColour(color)
        listCtrl.InsertItems([value],0)
        return listCtrl

    def _BuildTextCtrl(self, parent, font, color = wx.BLACK, value = "", selection = [0, 0]):
        if self._wordWrap:
            wordWrapStyle = wx.TE_WORDWRAP
        else:
            wordWrapStyle = wx.TE_DONTWRAP
        #textCtrl = wx.TextCtrl(parent, -1, pos = wx.DefaultPosition, size = parent.GetClientSize(), style = wx.TE_MULTILINE | wx.TE_RICH | wordWrapStyle)
        textCtrl = wx.TextCtrl(parent, -1, pos = wx.DefaultPosition, size = wx.Size(100,100), style = wx.TE_MULTILINE | wx.TE_RICH | wordWrapStyle)
        textCtrl.SetFont(font)
        textCtrl.SetForegroundColour(color)
        textCtrl.SetValue(value)
        return textCtrl


    def _GetFontAndColorFromConfig(self):
        font = wx.Font(10, wx.DEFAULT, wx.NORMAL, wx.NORMAL)
        config = wx.ConfigBase_Get()
        fontData = config.Read("TextEditorFont", "")
        if fontData:
            nativeFont = wx.NativeFontInfo()
            nativeFont.FromString(fontData)
            font.SetNativeFontInfo(nativeFont)
        color = wx.BLACK
        colorData = config.Read("TextEditorColor", "")
        if colorData:
            red = int("0x" + colorData[0:2], 16)
            green = int("0x" + colorData[2:4], 16)
            blue = int("0x" + colorData[4:6], 16)
            color = wx.Color(red, green, blue)
        return font, color


    def OnCreateCommandProcessor(self):
        # Don't create a command processor, it has its own
        pass


    def OnActivateView(self, activate, activeView, deactiveView):
        if activate and self._textCtrl:
            # In MDI mode just calling set focus doesn't work and in SDI mode using CallAfter causes an endless loop
            if self.GetDocumentManager().GetFlags() & wx.lib.docview.DOC_SDI:
                self._textCtrl.SetFocus()
            else:
                def SetFocusToTextCtrl():
                    if self._textCtrl:  # Need to make sure it is there in case we are in the closeall mode of the MDI window
                        self._textCtrl.SetFocus()
                wx.CallAfter(SetFocusToTextCtrl)

    def InitData(self):
        self._listCtrl.Clear()
        if self.GetDocument()._data :
            self.GetDocument().SetTitle('['+self._statusString+']'+self.GetDocument()._data._itemName)
            skuInfo = ''
            if self.GetDocument()._data._skuInfo is not None:
                skuInfo = self.GetDocument()._data._skuInfo
            self._listCtrl.InsertItems(
                ['开拍时间:  '+self.GetDocument()._data._startTimeStr,
                 '价格:      '+self.GetDocument()._data._price,
                 '剩余数量:  '+self.GetDocument()._data._quantityTotal+'  购买数量:  '+self.GetDocument()._data._quantityRequested.encode('gbk'),
                 '货品说明:  '+skuInfo
                 ]
                ,0)
            self._itemImageCtrl.LoadImage(self.GetDocument()._data._itemImage)
            self.OnChangeFilename()
        
        self._remainTimer = self.remainTimeTimer(self.GetDocument()._data._startTime, self._clockText, self._startTimeAheadInMs, self)
        self._remainTimer.Start(50)

    def OnUpdate(self, sender = None, hint = None):

        if wx.lib.docview.View.OnUpdate(self, sender, hint):
            return

    def OnClose(self, deleteWindow = True):
        if not wx.lib.docview.View.OnClose(self, deleteWindow):
            return False
        self.Activate(False)
        if deleteWindow and self.GetFrame():
            self.GetFrame().Destroy()
        return True

    #----------------------------------------------------------------------------
    # Methods for TextDocument to call
    #----------------------------------------------------------------------------

    def GetTextCtrl(self):
        return self._textCtrl


    #----------------------------------------------------------------------------
    # Format methods
    #----------------------------------------------------------------------------

    def OnChooseFont(self, event):
        data = wx.FontData()
        data.EnableEffects(True)
        data.SetInitialFont(self._textCtrl.GetFont())
        data.SetColour(self._textCtrl.GetForegroundColour())
        fontDialog = wx.FontDialog(self.GetFrame(), data)
        if fontDialog.ShowModal() == wx.ID_OK:
            data = fontDialog.GetFontData()
            self.SetFont(data.GetChosenFont(), data.GetColour())
        fontDialog.Destroy()


    def SetFont(self, font, color):
        self._textCtrl.SetFont(font)
        self._textCtrl.SetForegroundColour(color)
        self._textCtrl.Refresh()
        self._textCtrl.Layout()

    def _FindServiceHasString(self):
        findService = wx.GetApp().GetService(FindService.FindService)
        if not findService or not findService.GetFindString():
            return False
        return True

class TaskSettingDialog(wx.Dialog):
    def __init__(self, parent):
        wx.Dialog.__init__(self, parent, -1, _("账户管理"), pos=wx.DefaultPosition)
        sizer = wx.BoxSizer(wx.VERTICAL)
        self._accountInfoPanel = AccountInfoPanel(self,-1,AccountInfoPanel.GETADDR)
        sizer.Add(self._accountInfoPanel)
        sizer.Add(self.CreateButtonSizer(wx.OK|wx.CANCEL),0,wx.ALIGN_CENTER)
        self.SetSizer(sizer)
        wx.EVT_BUTTON(self,wx.ID_OK,self.OnOK)

    def OnOK(self,event):
        self._accountInfoPanel.OnOK(event)
        self.EndModal(wx.ID_OK)