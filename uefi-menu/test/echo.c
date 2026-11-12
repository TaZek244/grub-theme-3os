// Loader giả để thử: in tên và tham số nhận được rồi đứng yên
#include "../src/efi.h"
static EFI_GUID LIP = {0x5b1b31a1,0x9562,0x11d2,{0x8e,0x3f,0x00,0xa0,0xc9,0x69,0x72,0x3b}};
EFI_STATUS API efi_main(EFI_HANDLE h, EFI_SYSTEM_TABLE *st) {
    EFI_LOADED_IMAGE *li; st->ConOut->OutputString(st->ConOut, u"\r\nFAKE-LOADER-STARTED " TAG u" opts=[");
    if (!EFI_IS_ERR(st->BootServices->HandleProtocol(h, &LIP, (void**)&li)) && li->LoadOptions) st->ConOut->OutputString(st->ConOut, li->LoadOptions);
    st->ConOut->OutputString(st->ConOut, u"]\r\n");
    for (;;) st->BootServices->Stall(1000000);
}
