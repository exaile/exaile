
Var hwnd


Function architectureSelect

    ${Unless} ${RunningX64}
        StrCpy $INSTALL_ARCH "32"
        Abort
    ${EndIf}
    
    ; Don't let the user overwrite their current python installation
    ${If} $HAVE_PYTHON == "OK"
        StrCpy $INSTALL_ARCH $HAVE_PYTHON_ARCH
        Abort
    ${EndIf}
    
    StrCpy $INSTALL_ARCH "64"

    nsDialogs::Create /NOUNLOAD 1018
    Pop $0
    
    ${NSD_CreateLabel} 0% 0 100% 48% "Select preferred architecture for binaries (default should be correct)"
    Pop $0
    
    ${NSD_CreateRadioButton} 10% 48% 100% 8u "32-bit"
    Pop $hwnd
    ${NSD_AddStyle} $hwnd ${WS_GROUP}
    nsDialogs::SetUserData $hwnd "32"
    ${NSD_OnClick} $hwnd RadioClick
    
    ${NSD_CreateRadioButton} 10% 56% 100% 8u "64-bit"
    Pop $hwnd
    nsDialogs::SetUserData $hwnd "64"
    ${NSD_OnClick} $hwnd RadioClick
    ${NSD_SetState} $hwnd ${BST_CHECKED}

    nsDialogs::Show

FunctionEnd

Function RadioClick
    Pop $hwnd
    nsDialogs::GetUserData $hwnd
    Pop $INSTALL_ARCH
FunctionEnd
