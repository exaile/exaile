;---------------------------------------------------------------------
; ROUTINES TO DETECT PYTHON, PYGTK, PYGOBJECT, PYCAIRO and TCL/TK.
; - Taken from ASCEND NSIS installer (http://www.ascend4.org/)

;---------------------------------------------------------------------
; Look for Python in specific directory

Function DetectPython

    ; TODO: Really, we should be supporting more than one version here, but
    ;       given the python support from GST only supports 2.6... nope. 
    
    ; TODO: Really, assuming that the python path is a fixed location is
    ; a bit broken, but this installer is really geared towards non-technical
    ; users anyways, so the chances of them having it installed in a 
    ; non-default location is.. low, right? *hides from bugreports*

	${If} ${FileExists} "${PYTHON_PATH}\python.exe"
		StrCpy $HAVE_PYTHON "OK"
	${Else}
		;MessageBox MB_OK "No python.exe in $R6"
		StrCpy $HAVE_PYTHON "NOK"
	${EndIf}
FunctionEnd

Function DetectMutagen
    ${If} $HAVE_PYTHON == "OK"
        ; run python to see if its present
        ExecWait "${PYTHON_PATH}\pythonw.exe -c $\"import mutagen$\"" $0
        ${If} $0 != "0"
            ;MessageBox MB_OK "No mutagen module found"	
            StrCpy $HAVE_MUTAGEN "NOK"
        ${Else}
            StrCpy $HAVE_MUTAGEN "OK"
        ${EndIf}
    ${Else}
        ; If they don't have Python, they probably don't have mutagen.. 
        StrCpy $HAVE_MUTAGEN "NOK"
    ${EndIf}
FunctionEnd

;--------------------------------------------------------------------
; Are necessary PyGTK bits and pieces available?

;Function DetectPyGTK
;    ${If} ${FileExists} "${PYTHON_PATH}\Lib\site-packages\gtk-2.0\gtk\__init__.py"
;        StrCpy $HAVE_PYGTK "OK"
;    ${Else}
;        ;MessageBox MB_OK "No PyGTK in $PYPATH"		
;        StrCpy $HAVE_PYGTK "NOK"
;    ${EndIf}
;FunctionEnd

;--------------------------------------------------------------------
; GStreamer OSSBuild package detection

;Function DetectGstreamer
;    ReadEnvStr $0 OSSBUILD_GSTREAMER_DIR
;    ${IfNot} $0 == ""
;    	StrCpy $HAVE_GST "OK"
;	${Else}
;		StrCpy $HAVE_GST "NOK"
;	${EndIf}
;FunctionEnd

;Function DetectGstreamerSDK
;    ReadEnvStr $0 OSSBUILD_GSTREAMER_SDK_DIR
;    ${IfNot} $0 == ""
;    	StrCpy $HAVE_GSTSDK "OK"
;	${Else}
;		StrCpy $HAVE_GSTSDK "NOK"
;	${EndIf}
;FunctionEnd

;--------------------------------------------------------------------
; GStreamer.com SDK package detection

Function DetectGstreamerComSDK
    ReadEnvStr $0 GSTREAMER_SDK_ROOT_X86
    ${IfNot} $0 == ""
    	StrCpy $HAVE_GSTCOMSDK "OK"
	${Else}
		StrCpy $HAVE_GSTCOMSDK "NOK"
	${EndIf}
    
    ; TODO: What if they don't select the correct options? 
FunctionEnd

