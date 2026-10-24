# MU1367 / 791 AID 12.3

- Firmware gate: `/ifs/lsd.jxe` = **55,840,541 bytes**
- Display: **30 fps, navigation centered**
- Steering controls: short press zoom; long press map switch
- Profile core: `payload/profiles/MU1367/791/core.so`
- Fork patch: `core.so` and `common/altscreen-most-bridge` include the [block-artifact fix](../../patches/mu1367-791-artifact-fix/) and a safe area that keeps the turn card below the cluster status row

This is a standalone CarPlay Maps VC file set, not a complete toolbox. From this directory on the MMX shell, run `/bin/ksh ./run-install.sh`. The installer performs the exact firmware/profile check again and does not reboot automatically.

这是独立项目文件，不是完整工具箱。在 MMX 中进入本目录后运行 `/bin/ksh ./run-install.sh`；安装器会再次执行精确固件校验，且不会自动重启。
