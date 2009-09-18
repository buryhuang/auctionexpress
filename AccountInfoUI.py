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

#Customized Classes
import Utilities
from Utilities import LoginIntoTaobao
from Utilities import GlobalConfigParm
from Utilities import WebBitmap
from Utilities import TaobaoBrowser
from Utilities import TaobaoWorkerEvent
from Utilities import GetAddressMap
from Utilities import TaskData

_ = wx.GetTranslation

class ValidatePasswordDialog(wx.Dialog):
    def __init__(self, parent):
        wx.Dialog.__init__(self, parent, -1, _("密码验证"), pos=wx.DefaultPosition)
        sizer = wx.BoxSizer(wx.VERTICAL)
        self._accountInfoPanel = AccountInfoPanel(self,-1,AccountInfoPanel.GETPASS)
        sizer.Add(self._accountInfoPanel)
        sizer.Add(self.CreateButtonSizer(wx.OK|wx.CANCEL),0,wx.ALIGN_CENTER)
        self.SetSizer(sizer)
        wx.EVT_BUTTON(self,wx.ID_OK,self.OnOK)

    def OnOK(self,event):
        result = self._accountInfoPanel.OnGetAccountInfo(None)
        if result:
            self.EndModal(wx.ID_OK)

class AccountInfoPanel(wx.Panel):
    GETADDR=1
    GETPASS=2
    def __init__(self, parent, id, mode=GETADDR):
        wx.Panel.__init__(self, parent, id)
        SPACE = 10
        HALF_SPACE   = 5
        
        self._addrMap = dict()
        self._password = None
        self._account = None
        self._mode = mode
        
        #parent.AddPage(self,_('账户管理'))
        
        accountLabel = wx.StaticText(self, -1, _("账号:        "))
        self._accountComboCtrl = wx.ComboBox(self, -1, "", size = (125, -1))
        if self._mode == self.GETPASS:
            self._accountComboCtrl.SetEditable(False)
        self._accountComboCtrl.Bind(wx.EVT_COMBOBOX,self.OnChangeAccount)
        accountSizer = wx.BoxSizer(wx.HORIZONTAL)
        accountSizer.Add(accountLabel)
        accountSizer.Add(self._accountComboCtrl)
        if self._mode == self.GETADDR:
            self._removeAccountButton = wx.Button(self, -1, _("删除此账号信息"))
            self._removeAccountButton.Enable(False)
            accountSizer.Add(self._removeAccountButton)

        if mode == AccountInfoPanel.GETPASS:
            passLabel = wx.StaticText(self,-1,_('密码:'))
            self._passTextCtrl = wx.TextCtrl(self,-1,style=wx.TE_PASSWORD)
            passSizer = wx.BoxSizer(wx.HORIZONTAL)
            passSizer.Add(passLabel)
            passSizer.Add(self._passTextCtrl)
        elif mode == AccountInfoPanel.GETADDR:
            addrLabel = wx.StaticText(self, -1, _("送货地址:"))
            self._addrTextCtrl = wx.ListBox(self, -1, size = (400, 60))
            #self._addrTextCtrl.SetEditable(False)
            addrSizer = wx.BoxSizer(wx.HORIZONTAL)
            addrSizer.Add(addrLabel)
            addrSizer.Add(self._addrTextCtrl)
        
            self._getAccountInfoButton = wx.Button(self, -1, _("获取账号信息"))
            wx.EVT_BUTTON(self, self._getAccountInfoButton.GetId(), self.OnGetAccountInfo)
        
        #self._wordWrapCheckBox = wx.CheckBox(self, -1, _("Wrap words inside text area"))
        #self._wordWrapCheckBox.SetValue(wx.ConfigBase_Get().ReadInt("TextEditorWordWrap", True))

        textPanelBorderSizer = wx.BoxSizer(wx.VERTICAL)
        textPanelSizer = wx.BoxSizer(wx.VERTICAL)

        textFontSizer = wx.BoxSizer(wx.HORIZONTAL)

        textPanelSizer.Add(accountSizer, 0, wx.ALL, HALF_SPACE)
        if mode == AccountInfoPanel.GETPASS:
            textPanelSizer.Add(passSizer, 0, wx.ALL, HALF_SPACE)
        elif mode == AccountInfoPanel.GETADDR:
            textPanelSizer.Add(addrSizer, 0, wx.ALL, HALF_SPACE)
            textPanelSizer.Add(self._getAccountInfoButton, 0, wx.ALL, HALF_SPACE)
        #textPanelSizer.Add(self._wordWrapCheckBox, 0, wx.ALL, HALF_SPACE)
        
        textPanelBorderSizer.Add(textPanelSizer, 0, wx.ALL, SPACE)
        self.SetSizer(textPanelBorderSizer)

        #read existing info
        self._addrMap = GetAddressMap()
        for account in self._addrMap.keys():
            self._accountComboCtrl.Append(account)
            if self._mode == self.GETPASS:
                self._accountComboCtrl.SetSelection(0)

    def OnChangeAccount(self,event):
        #wx.MessageBox(self._accountComboCtrl.GetValue())
        account = self._accountComboCtrl.GetValue()
        if self._mode == self.GETADDR:
            self._addrTextCtrl.Clear()
            self._getAccountInfoButton.SetFocus()
            if self._addrMap[account]:
                for addr in self._addrMap[account]:
                    str = addr['AddressName']
                    str += ' - '
                    str += addr['AddressArea']
                    str += addr['AddressFull']
                    self._addrTextCtrl.Append(str)
        elif self._mode == self.GETPASS:
            self._passTextCtrl.SetFocus()

    def OnGetAccountInfo(self,event):
        #import Addresses first
        account = None
        password = None
        if not self._accountComboCtrl.GetValue():
            wx.MessageBox('请填入账号')
            return False
        else:
            account = self._accountComboCtrl.GetValue()
            #ask for password
            class PromptDlg(wx.Dialog):
                def OnMod(self,event):
                    self._password = self._passTextCtrl.GetValue()
                
                def __init__(self,parent):
                    self._password = None
                    wx.Dialog.__init__(self,parent,-1,_("请输入密码"),size=wx.Size(200,80))
                    self._passTextCtrl = wx.TextCtrl(self,-1,size=(150,-1),style=wx.TE_PASSWORD)
                    self._passTextCtrl.Bind(wx.EVT_TEXT,self.OnMod)
                    self._passTextCtrl.Show(True)
                    baseSizer = wx.BoxSizer(wx.VERTICAL)
                    baseSizer.Add(self._passTextCtrl,0,wx.ALIGN_CENTER)
                    baseSizer.Add(self.CreateButtonSizer(wx.OK|wx.CANCEL),0,wx.ALIGN_CENTER)
                    self.SetSizer(baseSizer)
                    baseSizer.Layout()
                    self._passTextCtrl.SetFocus()
            
            if self._mode == self.GETADDR:
                promptDlg = PromptDlg(self)
                if promptDlg.ShowModal() == wx.ID_OK:
                    if promptDlg._password != None and len(promptDlg._password) != 0:
                        password = promptDlg._password
                    else:
                        wx.MessageBox("密码不能为空")
                        return False
                else:
                    return False
            elif self._mode == self.GETPASS:
                if self._passTextCtrl.GetValue()!=None and len(self._passTextCtrl.GetValue())!=0:
                    password = self._passTextCtrl.GetValue()
                else:
                    wx.MessageBox("密码不能为空")
                    return False

        if self._mode == self.GETADDR:
            self._addrTextCtrl.Clear()
        browserAddr =  TaobaoBrowser()
        browserAddr.open('http://member1.taobao.com/member/deliver_address.htm')
        LoginIntoTaobao(browserAddr,account,password)

        p = re.compile('<table.*?AddressList.*?mytaobao-junk\">(.*?)<\/table>',re.S)
        addrListBlock = p.findall(browserAddr.contents)
        if addrListBlock:
            #<tr>
            #<td align="center">黄惠衡</td>
            #<td>广东省 广州市 天河区</td>
            #<td>科韵路16号广州信息港E栋网易大厦8楼</td>
            #<td>510665</td>
            #<td>0756-6880026 <br />13750065111</td>
            #<td><a href="#" onclick="selectDeliver(222667564)">修改</a>|<a href="#" onclick="del(222667564)">删除</a></td>
            #</tr>
            #print addrListBlock
            self._account = account
            self._password = password
            p = re.compile('<tr>.*?<td align=\"center\">(.*?)<\/td>.*?<td>(.*?)<\/td>.*?<td>(.*?)<\/td>.*?<td>(.*?)<\/td>.*?<td>(.*?)<\/td>.*?del\((\d+)\).*?删除.*?<\/a><\/td>.*?<\/tr>',re.S)
            addrList = p.findall(addrListBlock[0])
            if addrList:
                self._addrMap[account]=[]
                if self._accountComboCtrl.FindString(account) == wx.NOT_FOUND:
                    self._accountComboCtrl.Append(account)
                if self._mode == self.GETADDR:
                    self._addrTextCtrl.Clear()
            for addr in addrList:
                if self._mode == self.GETADDR:
                    self._addrTextCtrl.Append(str(addr[0]+' - '+addr[1]+addr[2]))
                #print addr[0]+' - '+addr[1]+addr[2]
                #self._addrMap[account].append([addr[0],addr[1],addr[2],addr[5]])
                self._addrMap[account].append(
                    {
                        'AddressName':addr[0],
                        'AddressArea':addr[1],
                        'AddressFull':addr[2],
                        'AddressPost':addr[3],
                        'AddressPhone':addr[4],
                        'AddressId'  :addr[5],
                    }
                )
        else:
            wx.MessageBox("无法获取地址,请确认帐号密码输入正确")
            return False
        
        #print self._addrMap
        return True

    def OnOK(self, optionsDialog):
        if(wx.MessageBox("是否保存新的地址数据?","确认",wx.YES|wx.NO) == wx.YES):
            config = wx.ConfigBase_Get()
            accounts = self._addrMap.keys()
            config.WriteInt("AccountNumber",len(accounts))
            for i in range(0,len(accounts)):
                config.Write("Account"+str(i),accounts[i])
                addrs = self._addrMap[accounts[i]]
                config.WriteInt("AddressNumber"+str(i),len(addrs))
                for j in range(0,len(addrs)):
                    config.Write("AddressName"+str(i)+"_"+str(j),self._addrMap[accounts[i]][j]['AddressName'])
                    config.Write("AddressArea"+str(i)+"_"+str(j),self._addrMap[accounts[i]][j]['AddressArea'])
                    config.Write("AddressFull"+str(i)+"_"+str(j),self._addrMap[accounts[i]][j]['AddressFull'])
                    config.Write("AddressPost"+str(i)+"_"+str(j),self._addrMap[accounts[i]][j]['AddressPost'])
                    config.Write("AddressPhone"+str(i)+"_"+str(j),self._addrMap[accounts[i]][j]['AddressPhone'])
                    config.Write("AddressId"+str(i)+"_"+str(j),self._addrMap[accounts[i]][j]['AddressId'])