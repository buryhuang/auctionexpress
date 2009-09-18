#!/usr/bin/env python
# coding: gbk

from zope.testbrowser.browser import Browser

import sys
import os.path
import wx
import wx.html
#import wx.lib.iewin
import wx.lib.docview as docview
import wx.lib.pydocview as pydocview
#import comtypes
import TextEditor
_ = wx.GetTranslation


#----------------------------------------------------------------------------
# Classes
#----------------------------------------------------------------------------
class AuctionDocManager (docview.DocManager):
    def MakeDefaultName(self):
        """
        Returns a suitable default name. This is implemented by appending an
        integer counter to the string "Untitled" and incrementing the counter.
        """
        name = _("Task %d") % self._defaultDocumentNameCounter
        self._defaultDocumentNameCounter = self._defaultDocumentNameCounter + 1
        return name

class AuctionTabbedFrame (wx.lib.pydocview.DocTabbedParentFrame):
    def __init__(self, manager, frame, id, title, pos = wx.DefaultPosition, size = wx.DefaultSize, style = wx.DEFAULT_FRAME_STYLE, name = "frame"):
        wx.lib.pydocview.DocTabbedParentFrame.__init__(self, manager, frame, id, title, pos, size, style, name)
        self._frame = frame
        wx.EVT_MENU(self, wx.ID_NEW, self.OnNew)
        
    def OnNew(self, event):
        taskDetailDialog = TextEditor.TaskDetailDialog(self)
        newAnswer = taskDetailDialog.ShowModal()
        if newAnswer == wx.ID_OK :
            self.ProcessEvent(event)
            #self.GetDocumentManager().OnFileNew(None)
            self.GetDocumentManager().GetCurrentDocument()._data=taskDetailDialog._data
            self.GetDocumentManager().GetCurrentView().InitData()

class TextEditorApplication(pydocview.DocApp):

    SPLASH = "splash.png"
    _stdClockText = None
    _ID_SETTING = wx.NewId()
    
    class StdClockTimer (wx.Timer):
        def Notify(self):
            try:
                if TextEditorApplication._stdClockText:
                    now = wx.DateTime.UNow()
                    TextEditorApplication._stdClockText.SetLabel(_('北京标准时间: ')+str(now)+" "+str(now.GetMillisecond()))
            except:
                #well, doesn't matter
                pass

    def OnSetting(self,event):
        settingDialog = TextEditor.TaskSettingDialog(self._frame)
        settingDialog.ShowModal()
        
    #override the default
    def OpenMainFrame(self):
        docManager = self.GetDocumentManager()
        if docManager.GetFlags() & wx.lib.docview.DOC_MDI:
            if self.GetUseTabbedMDI():
                frame = AuctionTabbedFrame(docManager, None, -1, self.GetAppName())
            else:
                frame = wx.lib.pydocview.DocMDIParentFrame(docManager, None, -1, self.GetAppName())
                
            self._frame = frame
            menuBar = frame.GetMenuBar()
            
            menuBar.Remove(0)
            menuBar.Remove(0)
            menuBar.Remove(0)
            
            taskMenu = wx.Menu()
            taskMenu.Append(wx.ID_NEW, _("新建抢拍任务(&N)"), _("新建一个抢拍任务"))
            taskMenu.Append(self._ID_SETTING,_("账号设置"),_("设置账号信息"))
            taskMenu.Append(wx.ID_EXIT, "退出(&X)", "退出应用程序")
            wx.EVT_MENU(self,self._ID_SETTING,self.OnSetting)
            
            menuBar.Insert(0,taskMenu, "任务(&T)")
            #frame.SetMenuBar(menuBar)
            
            #leave only NEW for now

            toolBar = frame.GetToolBar()
            
            toolBar.DeleteToolByPos(1);
            toolBar.DeleteToolByPos(1);
            toolBar.DeleteToolByPos(1);
            toolBar.DeleteToolByPos(1);
            toolBar.DeleteToolByPos(1);
            toolBar.DeleteToolByPos(1);
            toolBar.DeleteToolByPos(1);
            toolBar.DeleteToolByPos(1);
            toolBar.DeleteToolByPos(1);
            toolBar.DeleteToolByPos(1);
            toolBar.DeleteToolByPos(1);
            toolBar.DeleteToolByPos(1);
            
            toolBar.Realize()
            
            TextEditorApplication._stdClockText = wx.StaticText(toolBar, -1, pos = wx.Point(300,5), size = wx.Size(200,30), label=_("北京标准时间 22:52:00 .0000"))
            #frame.SetToolBar(toolBar)
            
            self._stdClockTimer.Start(1000)
            
            frame.Show(True)

    def OnInit(self):
        wx.Locale.AddCatalogLookupPathPrefix('locale')
        self._locale = wx.Locale(wx.LANGUAGE_CHINESE_SIMPLIFIED)
        self._locale.AddCatalog('test')
    
        # Call the super - this is important!!!
        pydocview.DocApp.OnInit(self)
        
        self._stdClockTimer = self.StdClockTimer()

        # Show the splash dialog while everything is loading up
        if os.path.exists(TextEditorApplication.SPLASH):
            self.ShowSplash(TextEditorApplication.SPLASH)

        # Set the name and the icon
        self.SetAppName(_("虫呙牛牛的淘宝秒杀器"))
        #self.SetDefaultIcon(pydocview.getBlankIcon())
        self.SetDefaultIcon(wx.Icon('icons/app.ico',wx.BITMAP_TYPE_ICO))
        
        # Initialize the document manager
        docManager = AuctionDocManager(flags = self.GetDefaultDocManagerFlags())  
        self.SetDocumentManager(docManager)

        # Create a template for text documents and associate it with the docmanager
        textTemplate = docview.DocTemplate(docManager,
                                              _("Text"),
                                              "*.text;*.txt",
                                              _("Text"),
                                              _(".txt"),
                                              _("Text Document"),
                                              _("Text View"),
                                              TextEditor.TextDocument,
                                              TextEditor.TextView,
                                              icon=pydocview.getBlankIcon())
        docManager.AssociateTemplate(textTemplate)

        # Install services - these can install menu and toolbar items
        #textService           = self.InstallService(TextEditor.TextService())
        #optionsService        = self.InstallService(pydocview.DocOptionsService(False,supportedModes=wx.lib.docview.DOC_MDI))
        windowMenuService     = self.InstallService(pydocview.WindowMenuService())
        filePropertiesService = self.InstallService(pydocview.FilePropertiesService())
        if os.path.exists(TextEditorApplication.SPLASH):
            aboutService      = self.InstallService(pydocview.AboutService(image=wx.Image(TextEditorApplication.SPLASH)))
        else:
            aboutService      = self.InstallService(pydocview.AboutService())
            
        # Install the TextEditor's option panel into the OptionsService
        #optionsService.AddOptionsPanel(TextEditor.TextOptionsPanel)

        # If it is an MDI app open the main frame
        self.OpenMainFrame()
        
        # Open any files that were passed via the command line
        self.OpenCommandLineArgs()
        
        # If nothing was opened and it is an SDI app, open up an empty text document
        if not docManager.GetDocuments() and docManager.GetFlags() & wx.lib.docview.DOC_SDI:
            textTemplate.CreateDocument('', docview.DOC_NEW).OnNewDocument()

        # Close the splash dialog
        if os.path.exists(TextEditorApplication.SPLASH):
            self.CloseSplash()
        
        # Show the tips dialog
        if os.path.exists("tips.txt"):
            wx.CallAfter(self.ShowTip, wx.GetApp().GetTopWindow(), wx.CreateFileTipProvider("tips.txt", 0))

        wx.UpdateUIEvent.SetUpdateInterval(1000)  # Overhead of updating menus was too much.  Change to update every N milliseconds.

        # Tell the framework that everything is great
        return True
    
    def OnDestroy(self):
        self._stdClockTimer.Stop()

#----------------------------------------------------------------------------
# Main
#----------------------------------------------------------------------------

# Run the TextEditorApplication and do not redirect output to the wxPython error dialog
app = TextEditorApplication(redirect=False)
app.MainLoop()
