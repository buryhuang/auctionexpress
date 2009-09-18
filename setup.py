from distutils.core import setup   
import glob
import py2exe   
includes = ["encodings", "encodings.*"]   
options = {"py2exe":   
            {   "compressed": 1,   
                "optimize": 2,   
                "includes": includes,   
                "bundle_files": 1
            }   
          }   
setup(      
    version = "0.0.1",   
    description = "Auction Express",   
    name = "search panda",   
    options = options,   
    zipfile=None,   
    windows=[{"script": "AuctionExpress.py", "icon_resources": [(1, "icons/app.ico")] }],     
    data_files=[(".", ["C:\\Python25\\lib\\site-packages\\wx-2.8-msw-unicode\\wx\\msvcp71.dll", "C:\\Python25\\lib\\site-packages\\wx-2.8-msw-unicode\\wx\\gdiplus.dll"])]       
  )