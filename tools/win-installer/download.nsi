;---------------------------------------------------------------------
; - Taken from ASCEND NSIS installer (http://www.ascend4.org/)

Var DAI_RET
Var DAI_MSG
Var DAI_TMPFILE
Var DAI_REMOVE

!macro downloadAndInstall DAI_NAME DAI_URL DAI_FN DAI_CMD
	Push $0
	Push $1

	StrCpy $DAI_RET ""
	StrCpy $DAI_REMOVE ""

	${If} ${FileExists} "${DAI_FN}"
		DetailPrint "Found local file ${DAI_FN}..."
		${If} ${Cmd} `MessageBox MB_ICONQUESTION|MB_YESNO "File ${DAI_FN} was found in the current directory, so it may not be necessary to download it now.$\n$\nWould you like to run this local copy of the installer?" IDYES `
			StrCpy $DAI_RET "success"
			StrCpy $DAI_TMPFILE "${DAI_FN}"
		${EndIf}
	${EndIf}
	
	${If} $DAI_RET != "success"
		DetailPrint "Downloading file ${DAI_FN}..."
		DetailPrint "URL: ${DAI_URL}"
		StrCpy $DAI_TMPFILE "$TEMP\${DAI_FN}"

		; Download files using the INETC plugin for NSIS, available from
		; http://nsis.sourceforge.net/Inetc_plug-in
		inetc::get /CAPTION "${DAI_FN}""${DAI_URL}" "$DAI_TMPFILE" /END
		Pop $DAI_RET ; return value = exit code, "OK" means OK
			
		${DoWhile} $DAI_RET != "OK"
			${If} $DAI_RET == "cancel"
				StrCpy $DAI_MSG "cancelled"
			${Else}
				StrCpy $DAI_MSG "failed (return '$DAI_RET')"
			${EndIf}
			
			DetailPrint "Download of ${DAI_FN} $DAI_MSG."
			${IfNot} ${Cmd} `MessageBox MB_ICONEXCLAMATION|MB_YESNO "${DAI_NAME} download $DAI_MSG. URL was:$\n$\n${DAI_URL}$\n$\nDo you wish to re-attempt the download?" IDYES `
				; response was no
				;MessageBox MB_OK "File ${DAI_NAME} will not be installed..."
				Pop $1
				Pop $0
				Push 1 ; error code
				Return
			${EndIf}
			
			;MessageBox MB_OK "Will re-attempt download of ${DAI_NAME}"
			${If} ${FileExists} "$DAI_TMPFILE"
				Delete "$DAI_TMPFILE"
			${EndIf}
		${Loop}
		
		StrCpy $DAI_REMOVE "1"
	${EndIf}
	

	;MessageBox MB_OK "Installing ${DAI_NAME}...$\n$\nCommand: ${DAI_CMD}"
	DetailPrint "Installing ${DAI_NAME} (${DAI_FN})"
	ExecWait "${DAI_CMD}" $0
	DetailPrint "Installer return code = $0"
	${If} $0 != "0"
		MessageBox MB_ICONEXCLAMATION|MB_OK "${DAI_NAME} installer returned a non-zero error code '$0'"
        Pop $1
        Pop $0
        Push 1 ; error code
    ${Else}
        Pop $1
        Pop $0
        Push 0 ; error code
	${EndIf}
	
	${If} $DAI_REMOVE != ""
		;MessageBox MB_OK "Deleting $DAI_TMPFILE..."
		Delete "$DAI_TMPFILE"
	${EndIf}
	
!macroend