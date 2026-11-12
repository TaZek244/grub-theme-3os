// Định nghĩa UEFI tối thiểu (chỉ phần Triboot dùng). Theo UEFI Spec 2.x, x86_64, ms_abi.
#pragma once
typedef unsigned char      u8;
typedef unsigned short     u16;
typedef unsigned int       u32;
typedef unsigned long long u64;
typedef signed short       i16;
typedef signed int         i32;
typedef signed long long   i64;
typedef u64                UINTN;
typedef u64                EFI_STATUS;
typedef void              *EFI_HANDLE;
typedef void              *EFI_EVENT;
typedef u16                CHAR16;

#define API __attribute__((ms_abi))
#define EFI_ERR(x)        (0x8000000000000000ULL | (x))
#define EFI_SUCCESS       0
#define EFI_LOAD_ERROR    EFI_ERR(1)
#define EFI_NOT_READY     EFI_ERR(6)
#define EFI_NOT_FOUND     EFI_ERR(14)
#define EFI_ABORTED       EFI_ERR(21)
#define EFI_IS_ERR(s)     ((i64)(s) < 0)

typedef struct { u32 d1; u16 d2, d3; u8 d4[8]; } EFI_GUID;

typedef struct { u64 Signature; u32 Revision, HeaderSize, CRC32, Reserved; } EFI_TABLE_HEADER;

typedef struct { u16 ScanCode; CHAR16 UnicodeChar; } EFI_INPUT_KEY;
#define SCAN_UP    1
#define SCAN_DOWN  2
#define SCAN_RIGHT 3
#define SCAN_LEFT  4
#define SCAN_ESC   0x17

typedef struct SIMPLE_INPUT {
    EFI_STATUS (API *Reset)(struct SIMPLE_INPUT *, u8);
    EFI_STATUS (API *ReadKeyStroke)(struct SIMPLE_INPUT *, EFI_INPUT_KEY *);
    EFI_EVENT WaitForKey;
} SIMPLE_INPUT;

typedef struct SIMPLE_OUTPUT {
    void *Reset;
    EFI_STATUS (API *OutputString)(struct SIMPLE_OUTPUT *, CHAR16 *);
    void *TestString, *QueryMode, *SetMode;
    EFI_STATUS (API *SetAttribute)(struct SIMPLE_OUTPUT *, UINTN);
    EFI_STATUS (API *ClearScreen)(struct SIMPLE_OUTPUT *);
    void *SetCursorPosition;
    EFI_STATUS (API *EnableCursor)(struct SIMPLE_OUTPUT *, u8);
    void *Mode;
} SIMPLE_OUTPUT;

typedef struct {
    u16 Year; u8 Month, Day, Hour, Minute, Second, Pad1;
    u32 Nanosecond; i16 TimeZone; u8 Daylight, Pad2;
} EFI_TIME;

typedef struct {
    EFI_TABLE_HEADER Hdr;
    EFI_STATUS (API *GetTime)(EFI_TIME *, void *);
    void *SetTime, *GetWakeupTime, *SetWakeupTime, *SetVirtualAddressMap, *ConvertPointer;
    void *GetVariable, *GetNextVariableName, *SetVariable, *GetNextHighMonotonicCount;
    void (API *ResetSystem)(u32 type, EFI_STATUS, UINTN, void *);
} EFI_RUNTIME_SERVICES;

#define ByProtocol 2
#define EfiLoaderData 2

typedef struct {
    EFI_TABLE_HEADER Hdr;
    void *RaiseTPL, *RestoreTPL;
    void *AllocatePages, *FreePages, *GetMemoryMap;
    EFI_STATUS (API *AllocatePool)(u32 type, UINTN size, void **buf);
    EFI_STATUS (API *FreePool)(void *);
    void *CreateEvent, *SetTimer, *WaitForEvent, *SignalEvent, *CloseEvent, *CheckEvent;
    void *InstallProtocolInterface, *ReinstallProtocolInterface, *UninstallProtocolInterface;
    EFI_STATUS (API *HandleProtocol)(EFI_HANDLE, EFI_GUID *, void **);
    void *Reserved, *RegisterProtocolNotify;
    void *LocateHandle, *LocateDevicePath, *InstallConfigurationTable;
    EFI_STATUS (API *LoadImage)(u8 boot_policy, EFI_HANDLE parent, void *dp, void *src, UINTN size, EFI_HANDLE *out);
    EFI_STATUS (API *StartImage)(EFI_HANDLE, UINTN *exit_size, CHAR16 **exit_data);
    void *Exit;
    EFI_STATUS (API *UnloadImage)(EFI_HANDLE);
    void *ExitBootServices, *GetNextMonotonicCount;
    EFI_STATUS (API *Stall)(UINTN us);
    EFI_STATUS (API *SetWatchdogTimer)(UINTN, u64, UINTN, CHAR16 *);
    EFI_STATUS (API *ConnectController)(EFI_HANDLE, EFI_HANDLE *, void *, u8);
    void *DisconnectController;
    void *OpenProtocol, *CloseProtocol, *OpenProtocolInformation, *ProtocolsPerHandle;
    EFI_STATUS (API *LocateHandleBuffer)(u32 type, EFI_GUID *, void *key, UINTN *n, EFI_HANDLE **buf);
    EFI_STATUS (API *LocateProtocol)(EFI_GUID *, void *, void **);
    void *InstallMultiple, *UninstallMultiple, *CalculateCrc32, *CopyMem, *SetMem, *CreateEventEx;
} EFI_BOOT_SERVICES;

typedef struct {
    EFI_TABLE_HEADER Hdr;
    CHAR16 *FirmwareVendor; u32 FirmwareRevision;
    EFI_HANDLE ConsoleInHandle;  SIMPLE_INPUT  *ConIn;
    EFI_HANDLE ConsoleOutHandle; SIMPLE_OUTPUT *ConOut;
    EFI_HANDLE StdErrHandle;     SIMPLE_OUTPUT *StdErr;
    EFI_RUNTIME_SERVICES *RuntimeServices;
    EFI_BOOT_SERVICES    *BootServices;
    UINTN NumberOfTableEntries; void *ConfigurationTable;
} EFI_SYSTEM_TABLE;

typedef struct {
    u32 Revision; EFI_HANDLE ParentHandle; EFI_SYSTEM_TABLE *SystemTable;
    EFI_HANDLE DeviceHandle; void *FilePath; void *Reserved;
    u32 LoadOptionsSize; void *LoadOptions;
    void *ImageBase; u64 ImageSize; u32 ImageCodeType, ImageDataType; void *Unload;
} EFI_LOADED_IMAGE;

// --- Đồ họa (GOP)
typedef struct { u8 Blue, Green, Red, Reserved; } EFI_BLT_PIXEL;
typedef struct {
    u32 Version, HorizontalResolution, VerticalResolution, PixelFormat;
    u32 RedMask, GreenMask, BlueMask, ReservedMask, PixelsPerScanLine;
} EFI_GOP_MODE_INFO;
typedef struct {
    u32 MaxMode, Mode; EFI_GOP_MODE_INFO *Info; UINTN SizeOfInfo;
    u64 FrameBufferBase; UINTN FrameBufferSize;
} EFI_GOP_MODE;
typedef struct GOP {
    EFI_STATUS (API *QueryMode)(struct GOP *, u32, UINTN *, EFI_GOP_MODE_INFO **);
    EFI_STATUS (API *SetMode)(struct GOP *, u32);
    EFI_STATUS (API *Blt)(struct GOP *, void *buf, u32 op, UINTN sx, UINTN sy, UINTN dx, UINTN dy, UINTN w, UINTN h, UINTN delta);
    EFI_GOP_MODE *Mode;
} GOP;
#define BltBufferToVideo 2

// --- File
typedef struct FILE {
    u64 Revision;
    EFI_STATUS (API *Open)(struct FILE *, struct FILE **, CHAR16 *, u64 mode, u64 attr);
    EFI_STATUS (API *Close)(struct FILE *);
    void *Delete;
    EFI_STATUS (API *Read)(struct FILE *, UINTN *, void *);
    void *Write;
    EFI_STATUS (API *GetPosition)(struct FILE *, u64 *);
    EFI_STATUS (API *SetPosition)(struct FILE *, u64);
} FILE;
typedef struct SFS {
    u64 Revision;
    EFI_STATUS (API *OpenVolume)(struct SFS *, FILE **);
} SFS;
#define FILE_MODE_READ 1

// --- Device path
typedef struct { u8 Type, SubType, Length[2]; } DP;
#define DP_MEDIA 4
#define DP_HD    1
#define DP_FILE  4
#define DP_END   0x7F
