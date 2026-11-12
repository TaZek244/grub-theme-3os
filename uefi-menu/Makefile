# Build Triboot UEFI bằng gcc + ld (i386pep) có sẵn trên Arch, không cần gnu-efi.
CFLAGS = -O2 -std=gnu11 -Wall -Wextra -Wno-unused-parameter -ffreestanding -fno-stack-protector -fno-stack-check \
         -mno-red-zone -fshort-wchar -fpie -fno-ident -fno-asynchronous-unwind-tables -mgeneral-regs-only -fno-builtin
out/triboot.efi: src/triboot.c src/efi.h
	@mkdir -p out
	gcc $(CFLAGS) -c src/triboot.c -o out/triboot.o
	ld -m i386pep --subsystem 10 -e efi_main --image-base 0x10000000 --dynamicbase -nostdlib out/triboot.o -o $@
clean:
	rm -f out/triboot.o out/triboot.efi
