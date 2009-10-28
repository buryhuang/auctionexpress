# coding: gbk
import wx
import wx.html
#import wx.lib.iewin
import wx.lib.docview
import wx.lib.pydocview
import string
import threading
from zope.testbrowser.browser import Browser
import re
import datetime

#Customized Classes
import Utilities
from Utilities import LoginIntoTaobao
from Utilities import GlobalConfigParm
from Utilities import WebBitmap
from Utilities import TaobaoBrowser
from Utilities import TaobaoWorkerEvent
from Utilities import GetAddressMap
from Utilities import TaskData

from AccountInfoUI import ValidatePasswordDialog

_ = wx.GetTranslation

class TaskDetailPanel(wx.Panel):

    def __init__(self, parent, id, externHandler,data=None):
        wx.Panel.__init__(self, parent, id)
        SPACE = 10
        HALF_SPACE   = 5
        config = wx.ConfigBase_Get()
        self._textFont = wx.Font(10, wx.DEFAULT, wx.NORMAL, wx.NORMAL)
        self._textColor = wx.BLACK
        self._externHandler = externHandler
        self._urlString = ''

        #
        self.SetBackgroundColour(wx.WHITE)

        #Page
        parent.AddPage(self, _("任务信息"))

        #UpperSizer0
        fontLabel = wx.StaticText(self, -1, _("Item Link:"))
        self._itemUrlTextCtrl = wx.TextCtrl(self, -1, "", size = (125, -1))
        if data:
            self._itemUrlTextCtrl.SetValue(str(data._itemUrl))
        
        retrieveDetailsButton = wx.Button(self, -1, _("获取货品信息..."))
        retrieveDetailsButton.SetBackgroundColour(wx.CYAN)
        wx.EVT_BUTTON(self, retrieveDetailsButton.GetId(), self.OnRetrieveDetails)
        
        textFontSizer = wx.BoxSizer(wx.HORIZONTAL)
        textFontSizer.Add(fontLabel, 0, wx.ALIGN_LEFT | wx.RIGHT | wx.TOP, HALF_SPACE)
        textFontSizer.Add(self._itemUrlTextCtrl, 0, wx.ALIGN_LEFT | wx.EXPAND | wx.RIGHT, HALF_SPACE)
        textFontSizer.Add(retrieveDetailsButton, 0, wx.ALIGN_RIGHT | wx.LEFT, HALF_SPACE)
                
        #UpperSizer1
        #self._loadDebugHtmlCheckBox = wx.CheckBox(self, -1, _("Load debug html page"))
        #self._loadDebugHtmlCheckBox.SetValue(False)

        #UpperSizer2 - Start Time
        startTimeLabel = wx.StaticText(self, -1, _("开始拍卖时间:"))
        self._startTimeTextCtrl = wx.TextCtrl(self, -1, "", size = (200, -1))
        self._startTimeTextCtrl.SetBackgroundColour(wx.CYAN)
        if data:
            self._startTimeTextCtrl.SetValue(str(data._startTimeStr))
        startTimeSizer = wx.BoxSizer(wx.HORIZONTAL)
        startTimeSizer.Add(startTimeLabel, 0, wx.ALIGN_LEFT | wx.RIGHT | wx.TOP, HALF_SPACE)
        startTimeSizer.Add(self._startTimeTextCtrl, 0, wx.ALIGN_LEFT | wx.EXPAND | wx.RIGHT, HALF_SPACE)

        #UpperSizer2 - End Time
        endTimeLabel = wx.StaticText(self, -1, _("拍卖结束时间:"))
        self._endTimeTextCtrl = wx.TextCtrl(self, -1, "", size = (200, -1))
        self._endTimeTextCtrl.SetEditable(False)
        if data:
            self._endTimeTextCtrl.SetValue(str(data._endTimeStr))
        endTimeSizer = wx.BoxSizer(wx.HORIZONTAL)
        endTimeSizer.Add(endTimeLabel, 0, wx.ALIGN_LEFT | wx.RIGHT | wx.TOP, HALF_SPACE)
        endTimeSizer.Add(self._endTimeTextCtrl, 0, wx.ALIGN_LEFT | wx.EXPAND | wx.RIGHT, HALF_SPACE)

        #UpperSizer3 - Price
        priceLabel = wx.StaticText(self, -1, _("一 口 价:"))
        self._priceTextCtrl = wx.TextCtrl(self, -1, "", size = (80, -1))
        self._priceTextCtrl.SetEditable(False)
        if data:
            self._priceTextCtrl.SetValue(data._price)
        priceSizer = wx.BoxSizer(wx.HORIZONTAL)
        priceSizer.Add(priceLabel, 0, wx.ALIGN_LEFT | wx.RIGHT | wx.TOP, HALF_SPACE)
        priceSizer.Add(self._priceTextCtrl, 0, wx.ALIGN_LEFT | wx.EXPAND | wx.RIGHT, HALF_SPACE)

        #UpperSizer4 - Quantity
        quantityLabel = wx.StaticText(self, -1, _("购买数量:"))
        self._quantityTextCtrl = wx.TextCtrl(self, -1, "", size = (50, -1))
        self._quantityTextCtrl.SetValue('1')
        self._quantityTextCtrl.SetBackgroundColour(wx.CYAN)
        if data:
            self._quantityTextCtrl.SetValue(data._quantityRequested)
        #quantitySizer = wx.BoxSizer(wx.HORIZONTAL)
        priceSizer.Add(quantityLabel, 0, wx.ALIGN_LEFT | wx.RIGHT | wx.TOP, HALF_SPACE)
        priceSizer.Add(self._quantityTextCtrl, 0, wx.ALIGN_LEFT | wx.EXPAND | wx.RIGHT, HALF_SPACE)

        #UpperSizer4 - Quantity Total
        quantityTotalLabel = wx.StaticText(self, -1, _("剩余数量:"))
        self._quantityTotalTextCtrl = wx.TextCtrl(self, -1, "", size = (50, -1))
        self._quantityTotalTextCtrl.SetValue('0')
        if data:
            self._quantityTotalTextCtrl.SetValue(data._quantityTotal)
        #quantityTotalSizer = wx.BoxSizer(wx.HORIZONTAL)
        priceSizer.Add(quantityTotalLabel, 0, wx.ALIGN_LEFT | wx.RIGHT | wx.TOP, HALF_SPACE)
        priceSizer.Add(self._quantityTotalTextCtrl, 0, wx.ALIGN_LEFT | wx.EXPAND | wx.RIGHT, HALF_SPACE)

        #UpperSizer5 - Item Name
        itemNameLabel = wx.StaticText(self, -1, _("货品名称:"))
        self._itemNameTextCtrl = wx.TextCtrl(self, -1, "", size = (350, -1))
        self._itemNameTextCtrl.SetEditable(False)
        if data:
            self._itemNameTextCtrl.SetValue(data._itemName)
        itemNameSizer = wx.BoxSizer(wx.HORIZONTAL)
        itemNameSizer.Add(itemNameLabel, 0, wx.ALIGN_LEFT | wx.RIGHT | wx.TOP, HALF_SPACE)
        itemNameSizer.Add(self._itemNameTextCtrl, 0, wx.ALIGN_LEFT | wx.EXPAND | wx.RIGHT, HALF_SPACE)

        self._addrMap = GetAddressMap()
        #UpperSizer5 - Account
        accountLabel = wx.StaticText(self, -1, _("帐号:"))
        self._accountChoiceCtrl = wx.Choice(self, -1, size = wx.Size(200,-1), pos=wx.DefaultPosition)
        self._accountChoiceCtrl.Enable(False)
        self._accountChoiceCtrl.SetBackgroundColour(wx.CYAN)
        self._accountChoiceCtrl.Bind(wx.EVT_CHOICE, self.OnChangeAccount)
        for account in self._addrMap.keys():
            self._accountChoiceCtrl.Append(account)
        if data:
            self._accountChoiceCtrl.SetSelection(self._accountChoiceCtrl.FindString(data._account))
        accountSizer = wx.BoxSizer(wx.HORIZONTAL)
        accountSizer.Add(accountLabel, 0, wx.ALIGN_LEFT | wx.RIGHT | wx.TOP, HALF_SPACE)
        accountSizer.Add(self._accountChoiceCtrl, 0, wx.ALIGN_LEFT | wx.EXPAND | wx.RIGHT, HALF_SPACE)

        #UpperSizer5 - Password
        passwordLabel = wx.StaticText(self, -1, _("密码:"))
        self._passwordTextCtrl = wx.TextCtrl(self, -1, "", size = (200, -1),style=wx.TE_PASSWORD)
        self._passwordTextCtrl.Enable(False)
        self._passwordTextCtrl.SetBackgroundColour(wx.CYAN)
        if data:
            self._passwordTextCtrl.SetValue(data._password)
        self._passwordButton = wx.Button(self,-1,_("按此选择账号并输入密码"))
        self._passwordButton.SetBackgroundColour(wx.CYAN)
        self._passwordButton.Bind(wx.EVT_BUTTON,self.OnValidatePassword)
        passwordSizer = wx.BoxSizer(wx.HORIZONTAL)
        passwordSizer.Add(passwordLabel, 0, wx.ALIGN_LEFT | wx.RIGHT | wx.TOP, HALF_SPACE)
        passwordSizer.Add(self._passwordTextCtrl, 0, wx.ALIGN_LEFT | wx.EXPAND | wx.RIGHT, HALF_SPACE)
        passwordSizer.Add(self._passwordButton, 0, wx.ALIGN_LEFT | wx.EXPAND | wx.RIGHT, HALF_SPACE)

        #UpperSizer5 - Addresses
        addressLabel = wx.StaticText(self, -1, _("收货地址:"))
        self._addressChoiceCtrl = wx.Choice(self, -1, size = wx.Size(400,-1), pos=wx.DefaultPosition)
        self._addressChoiceCtrl.SetBackgroundColour(wx.CYAN)
        self._addressChoiceCtrl.Enable(False)
        addressSizer = wx.BoxSizer(wx.HORIZONTAL)
        if data:
            self.OnChangeAccount(None)
            self._addressChoiceCtrl.SetSelection(self._addressChoiceCtrl.FindString(data._addrDisplayStr))
        addressSizer.Add(addressLabel, 0, wx.ALIGN_LEFT | wx.RIGHT | wx.TOP, HALF_SPACE)
        addressSizer.Add(self._addressChoiceCtrl, 0, wx.ALIGN_LEFT | wx.EXPAND | wx.RIGHT, HALF_SPACE)

        #UpperSizer - Item Choices
        choiceSizer = wx.BoxSizer(wx.VERTICAL)
        self._itemChoiceLabels = []
        self._itemChoiceCtrls = []
        self._itemChoiceSizers = []
        for i in range(0,4):
            itemChoiceLabel = wx.StaticText(self, -1, _("可选类别"+str(i)+":"))
            self._itemChoiceLabels.append(itemChoiceLabel)
            itemChoiceCtrl = wx.Choice(self, -1, size = wx.DefaultSize, pos=wx.DefaultPosition)
            itemChoiceCtrl.Enable(False)
            self._itemChoiceCtrls.append(itemChoiceCtrl)
            itemChoiceSizer = wx.BoxSizer(wx.HORIZONTAL)
            itemChoiceSizer.Add(itemChoiceLabel, 0, wx.ALIGN_LEFT | wx.RIGHT | wx.TOP, HALF_SPACE)
            itemChoiceSizer.Add(self._itemChoiceCtrls[i], 0, wx.ALIGN_LEFT | wx.EXPAND | wx.RIGHT, HALF_SPACE)
            #self._itemChoiceSizers.append(itemChoiceSizer)
            choiceSizer.Add(itemChoiceSizer)
        if data:
            self.FillItemChoicesCtrl(data._itemChoices)
            for i in range(0,len(self._itemChoiceCtrls)):
                if data._itemChoiceIndexs[i] >=0 :
                    self._itemChoiceCtrls[i].SetSelection(data._itemChoiceIndexs[i])

        #UpperSizer6 - Item Image
        self._itemImageWindow =  WebBitmap(self,-1,size=wx.Size(200,100))
        if data:
            self._itemImageWindow.LoadImage(data._itemImage)
            
        #choice + image Sizer
        choiceAndImageSizer = wx.BoxSizer(wx.HORIZONTAL)
        choiceAndImageSizer.Add(choiceSizer)
        choiceAndImageSizer.Add(self._itemImageWindow)

        #Base Panel
        textPanelSizer = wx.BoxSizer(wx.VERTICAL)
        textPanelSizer.Add(textFontSizer, 0, wx.ALL, HALF_SPACE) #Upper0
        #textPanelSizer.Add(self._loadDebugHtmlCheckBox, 0, wx.ALL, HALF_SPACE) #Upper1
        textPanelSizer.Add(startTimeSizer, 0, wx.ALL, HALF_SPACE) #Upper2
        textPanelSizer.Add(endTimeSizer, 0, wx.ALL, HALF_SPACE) #Upper3
        textPanelSizer.Add(priceSizer, 0, wx.ALL, HALF_SPACE) #Upper3
        #textPanelSizer.Add(quantitySizer, 0, wx.ALL, HALF_SPACE) #Upper3
        #textPanelSizer.Add(quantityTotalSizer, 0, wx.ALL, HALF_SPACE) #Upper3
        textPanelSizer.Add(itemNameSizer, 0, wx.ALL, HALF_SPACE) #Upper3
        textPanelSizer.Add(choiceAndImageSizer,0,wx.ALL,HALF_SPACE) #choice and Image
        textPanelSizer.Add(accountSizer, 0, wx.ALL, HALF_SPACE) #Upper3
        textPanelSizer.Add(passwordSizer, 0, wx.ALL, HALF_SPACE) #Upper3
        textPanelSizer.Add(addressSizer, 0, wx.ALL, HALF_SPACE) #Upper3
        
        #Assemble onto Border
        textPanelBorderSizer = wx.BoxSizer(wx.VERTICAL)
        textPanelBorderSizer.Add(textPanelSizer, 0, wx.ALL, SPACE)
        
        self.SetSizer(textPanelBorderSizer)

        if not data:
            wx.Clipboard.Get().Open()
            textObj = wx.TextDataObject()
            if wx.Clipboard.Get().GetData(textObj):
                import re
                p = re.compile('^http:\/\/.*?taobao')
                if p.match(textObj.GetText()):
                    self._urlString = textObj.GetText()
            self._itemUrlTextCtrl.SetValue(self._urlString)
            wx.Clipboard.Get().Close()

    def FillItemChoicesCtrl(self, itemChoices):
        labelIndex=0
        choicesCount = 0
        for choiceGroup in itemChoices :
            choicesCount+=1
            #print choiceGroup[1]
            self._itemChoiceLabels[labelIndex].SetLabel(str(choiceGroup[0]))
            choiceCtrl = self._itemChoiceCtrls[labelIndex]
            choiceCtrl.Clear()
            choiceCtrl.Enable(True)
            choiceCtrl.SetBackgroundColour(wx.CYAN)
            p = re.compile('<li data-value=\"(.*?)\".*?<span>(.*?)<\/span>.*?<\/li>',re.S)
            itemSingleChoices = p.findall(choiceGroup[1])
            for singleChoice in itemSingleChoices:
                #print singleChoice
                choiceCtrl.Append(singleChoice[1])
                curIdx = choiceCtrl.FindString(singleChoice[1])
                choiceCtrl.SetClientData(curIdx,singleChoice)
            labelIndex+=1

        return choicesCount

    def OnValidatePassword(self,event):
        pwdDlg = ValidatePasswordDialog(self)
        res = pwdDlg.ShowModal()
        if res == wx.ID_OK:
            self._accountChoiceCtrl.SetSelection(self._accountChoiceCtrl.FindString(pwdDlg._accountInfoPanel._account))
            self.OnChangeAccount(None)
            self._passwordTextCtrl.SetValue(pwdDlg._accountInfoPanel._password)
            self._addressChoiceCtrl.Enable(True)

    def OnChangeAccount(self,event):
        account = self._accountChoiceCtrl.GetStringSelection()
        self._addressChoiceCtrl.Clear()
        if self._addrMap[account]:
            for addr in self._addrMap[account]:
                str = addr['AddressName']
                str += ' - '
                str += addr['AddressArea']
                str += addr['AddressFull']
                self._addressChoiceCtrl.Append(str)

    def OnRetrieveDetails(self, event):
        if hasattr(self._externHandler, 'OnRetrieveDetails'):
            #self._externHandler.OnRetrieveDetails(self._itemUrlTextCtrl.GetValue(), self._loadDebugHtmlCheckBox.GetValue())
            self._externHandler.OnRetrieveDetails(self._itemUrlTextCtrl.GetValue(), False)
        self.Layout()
        self.Refresh()


class TaskDetailDialog(wx.Dialog):

    def __init__(self, parent, data=None):
        wx.Dialog.__init__(self, parent, -1, _("Task Detail"), pos=wx.DefaultPosition)
        
        HALF_SPACE = 5
        SPACE = 10
        
        self._baseNotebook = None
        self._detailPanel = None
        self._rawHtmlPanel = None
        self._valid = False
        self._choicesCount = 0
        self._skuMap = None
        self._itemChoiceIndexs = [-1]*4
        
        self.SetBackgroundColour(wx.BLACK)
        
        if data == None:
            self._data = TaskData()
        else:
            self._data = data
            self._skuMap = data._skuMap
            self._itemChoices = data._itemChoices
            self._itemChoiceIndexs = data._itemChoiceIndexs[:]

        wx.EVT_BUTTON(self, wx.ID_OK, self.OnOK)

        sizer = wx.BoxSizer(wx.VERTICAL)

        if wx.Platform == "__WXMAC__":
            self._baseNotebook = wx.Listbook(self, wx.NewId(), style=wx.LB_DEFAULT)
        else:
            self._baseNotebook = wx.Notebook(self, wx.NewId(), style=wx.NB_MULTILINE)  # NB_MULTILINE is windows platform only
            

        self._detailPanel = TaskDetailPanel(self._baseNotebook,-1,self,data)
        #self._rawHtmlPanel = wx.lib.iewin.IEHtmlWindow(self._baseNotebook,-1,size=wx.Size(400,500))
        #self._baseNotebook.AddPage(self._rawHtmlPanel,"Raw Html")
        #self._rawHtmlPanel.LoadPage('c:\\CallpLog.html')
        
        self._detailPanel._startTimeTextCtrl.Bind(wx.EVT_TEXT, self.OnModifyStartTime)
        self._detailPanel._quantityTextCtrl.Bind(wx.EVT_TEXT, self.OnModifyOther)
        #self._detailPanel._accountChoiceCtrl.Bind(wx.EVT_CHOICE, self.OnModify)
        self._detailPanel._passwordTextCtrl.Bind(wx.EVT_TEXT, self.OnModifyOther)
        
        for ctrl in self._detailPanel._itemChoiceCtrls:
            ctrl.Bind(wx.EVT_CHOICE, self.OnChangeChoice)

        sizer.Add(self._baseNotebook, 0, wx.ALL | wx.EXPAND, SPACE)

        sizer.Add(self.CreateButtonSizer(wx.OK | wx.CANCEL), 0, wx.ALIGN_RIGHT | wx.RIGHT | wx.BOTTOM, HALF_SPACE)

        self._okButton = self.FindWindowById(wx.ID_OK)
        if not data:
            self._okButton.Enable(False)

        self.SetSizer(sizer)
        self.Layout()
        self.Fit()
        wx.CallAfter(self.DoRefresh)

    def OnModifyStartTime(self,event):
        self._data._startTimeStr = self._detailPanel._startTimeTextCtrl.GetValue().encode("gbk")
        self._data._startTime = Utilities.StringToDatetime(self._detailPanel._startTimeTextCtrl.GetValue())

    def OnModifyOther (self, event) :
        self._data._quantityRequested = self._detailPanel._quantityTextCtrl.GetValue()
        self._data._password= self._detailPanel._passwordTextCtrl.GetValue()
    
    def OnChangeChoice(self,event):
        #if the bid has not started, no info will be available
        #if self._data._startTime is not None and datetime.datetime.now() >= self._data._startTime and self._skuMap:
        self._itemChoiceIndexs = [-1]*4

        if self._skuMap:
            #print datetime.datetime.now()
            #print self._data._startTime
            skuMap = self._skuMap[:]
            #print skuMap
        
            itemKey = ''
            self._data._skuId = None
            self._data._skuInfo = ''
            
            if self._choicesCount>0:
                for i in range (0,self._choicesCount):
                    #print str(i)+":"+self._detailPanel._itemChoiceCtrls[i].GetStringSelection()
                    choiceCtrl = self._detailPanel._itemChoiceCtrls[i]
                    curIdx = choiceCtrl.GetSelection()
                    if curIdx != wx.NOT_FOUND:
                        self._itemChoiceIndexs[i]=curIdx
                        itemInfo = choiceCtrl.GetClientData(curIdx)
                        itemKey += ';'+str(itemInfo[0])
                        self._data._skuInfo+= \
                            self._detailPanel._itemChoiceLabels[i].GetLabel().encode('gbk') \
                            +':'
                        self._data._skuInfo += itemInfo[1]
                        self._data._skuInfo += ';'
            itemKey+=';'
            #print 'itemkey:'+itemKey
            
            notFound = True
            for mapTuple in skuMap:
                #print 'mapTuple'
                #print mapTuple
                if mapTuple[0]== itemKey:
                    notFound = False
                    #print "found:"+str(mapTuple)
                    self._data._skuId = str(mapTuple[1])
                    self._detailPanel._priceTextCtrl.SetValue(mapTuple[2])
                    self._detailPanel._quantityTotalTextCtrl.SetValue(mapTuple[3])
                    self._data._quantityTotal = mapTuple[3]
            #print 'skuid:'+str(self._data._skuId)
            #print 'skuInfo:'+str(self._data._skuInfo)
            if notFound:
                self._detailPanel._quantityTotalTextCtrl.SetValue('0')
                self._okButton.Enable(False)
            else:
                self._okButton.Enable(True)
    
    def OnRetrieveDetails(self, urlString, loadDebugHtml):
        #wx.MessageBox(urlString)
        #urlString = 'http://'
        import re
        
        p = re.compile('^http:\/\/')
        if p.match(urlString):
            self._data._itemUrl = urlString
            browser=TaobaoBrowser(urlString)
            
            foundItems = 0

            p = re.compile('\"([\d:;]+)\":\{.*?\"skuId\" : \"(.*?)\".*?\"price\" : \"(.*?)\".*?\"stock\" : \"(.*?)\".*?\}',re.S)
            self._skuMap = p.findall(browser.contents)
            if self._skuMap:
                foundItems += 1
                #print self._skuMap
            
            p = re.compile('开始:.*?(\d+年.*?\d秒).*?结束:.*?(\d+年.*?\d秒)',re.S)
            startEndTimes = p.findall(browser.contents)
            if len(startEndTimes)>0 and len(startEndTimes[0]) >= 2 :
                self._detailPanel._startTimeTextCtrl.SetValue(str(startEndTimes[0][0]))
                self._data._startTimeStr = str(startEndTimes[0][0])
                self._detailPanel._endTimeTextCtrl.SetValue(str(startEndTimes[0][1]))
                self._data._endTimeStr = str(startEndTimes[0][1])
                foundItems += 1

            p = re.compile('一 口 价.*?>([\d]+\.\d\d).*?元',re.S)
            price = p.findall(browser.contents)
            if len(price)>0 :
                self._detailPanel._priceTextCtrl.SetValue(str(price[0]))
                self._data._price = str(price[0])
                foundItems += 1

            #for in stock: id=J_SpanStock>35</SPAN>件)
            #new: span id="J_SpanStock" class="count">3</span>件)
            p = re.compile('J_SpanStock\" class=\"count\">(\d+)<\/span>件',re.S)
            quantityTotal = p.findall(browser.contents)
            if len(quantityTotal)>0 :
                self._detailPanel._quantityTotalTextCtrl.SetValue(str(quantityTotal[0]))
                self._data._quantityTotal = str(quantityTotal[0])
                foundItems += 1
            else:
                #for not started: 宝贝数量：</SPAN><EM>5件</EM>
                #what the hell
                p = re.compile('(\d+)件',re.S)
                quantityTotal = p.findall(browser.contents)
                #print quantityTotal
                if len(quantityTotal)>0 :
                    self._detailPanel._quantityTotalTextCtrl.SetValue(str(quantityTotal[0]))
                    self._data._quantityTotal = str(quantityTotal[0])
                    foundItems += 1


            p = re.compile('detail-hd.*?<h3>\s+(.*?)\s+<\/h3>',re.S)
            itemName = p.findall(browser.contents)
            if len(itemName)>0 :
                self._detailPanel._itemNameTextCtrl.SetValue(str(itemName[0]))
                self._data._itemName = str(itemName[0])
                foundItems += 1

            p = re.compile('<ul data-property=\"(.*?)\" class.*?J_ulSaleProp.*?>(.*?)<\/ul>',re.S)
            self._itemChoices = p.findall(browser.contents)
            #print itemChoices
            self._choicesCount = self._detailPanel.FillItemChoicesCtrl(self._itemChoices)
            if self._choicesCount> 0:
                foundItems += 1

            p = re.compile('J_ImgBooth\" src=\"(.*?)\"',re.S)
            imageUrl = p.findall(browser.contents)
            if len(imageUrl)>0 :
                #wx.MessageBox(str(imageUrl[0]))
                if self._detailPanel._itemImageWindow.Load(str(imageUrl[0])):
                    self._data._itemImage = self._detailPanel._itemImageWindow._image
                    foundItems += 1
                
            if foundItems <=3 :
                wx.MessageBox('商品链接可能不正确,无法获取商品信息,可以查看Debug Html以确认')
            else :
                self._valid = True
                self._okButton.Enable(True)

            if loadDebugHtml :
                try:
                    self._rawHtmlPanel.LoadString(browser.contents)
                except:
                    wx.MessageBox('Error loading debug page, you can just ignore it. It does no harm.')
        else:
            wx.MessageBox('Invalid link')

    def DoRefresh(self):
        """
        wxBug: On Windows XP when using a multiline notebook the default page doesn't get
        drawn, but it works when using a single line notebook.
        """
        self.Refresh()

    def GetDocManager(self):
        """
        Returns the document manager passed to the OptionsDialog constructor.
        """
        return self._docManager

    def OnOK(self, event):
        
        if self._detailPanel._quantityTotalTextCtrl.GetValue() == '0':
            wx.MessageBox("此货品数量不足")
            return

        #print 'choiceCount'+str(self._choicesCount)
        #when we get here, previous validation passed
        #so we need to reset to check choices
        self._valid = True
        missingData = '请填写如下数据:'
        if self._choicesCount>0:
            for i in range (0,self._choicesCount):
                #print str(i)+":"+self._detailPanel._itemChoiceCtrls[i].GetStringSelection()
                if self._detailPanel._itemChoiceCtrls[i].GetSelection()==wx.NOT_FOUND:
                    self._valid=False
                    missingData += ' '.encode('gbk')+self._detailPanel._itemChoiceLabels[i].GetLabel().encode('gbk')
        
        if self._detailPanel._accountChoiceCtrl.GetSelection() == wx.NOT_FOUND:
            self._valid=False
            missingData += ' 帐号'

        if self._detailPanel._passwordTextCtrl.GetValue() == "":
            self._valid=False
            missingData += ' 密码'

        if self._detailPanel._addressChoiceCtrl.GetSelection() == wx.NOT_FOUND:
            self._valid=False
            missingData += ' 收货地址'
                    
        if self._valid:
            self._data._account= self._detailPanel._accountChoiceCtrl.GetStringSelection()
            self._data._skuMap = self._skuMap
            self._data._itemChoices = self._itemChoices
            self._data._itemChoiceIndexs = self._itemChoiceIndexs[:]
            self._data._addrDisplayStr = self._detailPanel._addressChoiceCtrl.GetStringSelection()
            self._data._addrIndex = self._detailPanel._addressChoiceCtrl.GetSelection()
            self.EndModal(wx.ID_OK)
        else:
            wx.MessageBox(missingData)