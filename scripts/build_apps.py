#!/usr/bin/env python3
import os
import sys
import subprocess
import shutil
import argparse
import json
try:
    import yaml
except ImportError:
    yaml = None
from pathlib import Path

def run_cmd(cmd, cwd=None, check=True, shell=False):
    print(f"--> {' '.join(cmd) if isinstance(cmd, list) else cmd}")
    use_shell = shell or isinstance(cmd, str)
    res = subprocess.run(cmd, cwd=cwd, shell=use_shell, capture_output=True, text=True)
    if check and res.returncode != 0:
        print(f"Error (code {res.returncode}):\n{res.stderr}\n{res.stdout}")
        sys.exit(res.returncode)
    return res

def find_toolchain(prefix=None):
    if prefix:
        return prefix
    # Check PATH first
    gcc = shutil.which("xtensa-esp32s3-elf-gcc")
    if gcc:
        return gcc[:-3]
    # Check default platformio location
    home = os.path.expanduser("~")
    pio_path = os.path.join(home, ".platformio/packages/toolchain-xtensa-esp32s3/bin/xtensa-esp32s3-elf-")
    if os.path.exists(pio_path + "gcc"):
        return pio_path
    # Check /opt/xtensa-esp32s3-elf/bin/
    opt_path = "/opt/xtensa-esp32s3-elf/bin/xtensa-esp32s3-elf-"
    if os.path.exists(opt_path + "gcc"):
        return opt_path
    raise RuntimeError("xtensa-esp32s3-elf toolchain not found! Please set --toolchain-prefix")

def main():
    parser = argparse.ArgumentParser(description="Build Flipper FAP apps for ESP32")
    parser.add_argument("--config", default="apps.yaml", help="Path to apps.yaml")
    parser.add_argument("--fw-dir", default=None, help="Path to ESP32 firmware repository")
    parser.add_argument("--pio-libs", default=None, help="Path to ESP32-S3 framework libraries")
    parser.add_argument("--toolchain-prefix", default=None, help="Toolchain prefix (e.g. xtensa-esp32s3-elf-)")
    parser.add_argument("--output-dir", default="dist", help="Output directory for compiled FAPs and catalog")
    parser.add_argument("--app", default=None, help="Build only specific app ID")
    args = parser.parse_args()

    project_root = Path(__file__).resolve().parent.parent
    config_file = args.config
    if config_file == "apps.yaml" and not yaml and (project_root / "apps.json").exists():
        config_file = "apps.json"
    config_path = project_root / config_file
    with open(config_path, "r", encoding="utf-8") as f:
        if config_path.suffix == ".json" or yaml is None:
            config = json.load(f)
        else:
            config = yaml.safe_load(f)

    fw_dir = Path(args.fw_dir) if args.fw_dir else project_root / "firmware"
    if not fw_dir.exists():
        # Fallback to env or local reference if exists
        env_fw = os.environ.get("FW_DIR")
        local_ref = Path(env_fw) if env_fw else Path.home() / "projects/qMobile/references/esp32_firmware"
        if local_ref.exists():
            fw_dir = local_ref
        else:
            print("Cloning Sor3nt/Flipper-Zero-ESP32-Port reference...")
            run_cmd(["git", "clone", "--depth", "1", "https://github.com/Sor3nt/Flipper-Zero-ESP32-Port.git", str(fw_dir)])

    tc_prefix = find_toolchain(args.toolchain_prefix)
    CC = f"{tc_prefix}gcc"
    LD = f"{tc_prefix}ld"
    OBJCOPY = f"{tc_prefix}objcopy"
    NM = f"{tc_prefix}nm"

    out_dir = project_root / args.output_dir
    builds_dir = out_dir / "builds"
    icons_dir = out_dir / "icons"
    builds_dir.mkdir(parents=True, exist_ok=True)
    icons_dir.mkdir(parents=True, exist_ok=True)

    cache_dir = project_root / ".cache"
    cache_dir.mkdir(parents=True, exist_ok=True)

    # Core include directories
    includes = [
        f"-I{fw_dir}/components/compat",
        f"-I{fw_dir}/components",
        f"-I{fw_dir}",
        f"-I{fw_dir}/components/furi",
        f"-I{fw_dir}/components/furi/core",
        f"-I{fw_dir}/components/mlib",
        f"-I{fw_dir}/components/toolbox",
        f"-I{fw_dir}/components/storage",
        f"-I{fw_dir}/components/input",
        f"-I{fw_dir}/components/gui",
        f"-I{fw_dir}/components/gui/modules",
        f"-I{fw_dir}/components/gui/modules/widget_elements",
        f"-I{fw_dir}/components/notification",
        f"-I{fw_dir}/components/assets",
        f"-I{fw_dir}/components/loader",
        f"-I{fw_dir}/applications/services",
        f"-I{fw_dir}/components/flipper_application",
        f"-I{fw_dir}/components/furi_hal",
        f"-I{fw_dir}/components/furi_hal/boards",
        f"-I{fw_dir}/components/ble_profile",
        f"-I{fw_dir}/components/ble_profile/extra_profiles",
        f"-I{fw_dir}/components/furi_ble",
        f"-I{fw_dir}/components/ble_serial",
        f"-I{fw_dir}/components/bt",
    ]

    # Additional IDF headers from platformio or toolchain sysroot
    pio_libs = None
    candidates = []
    if args.pio_libs:
        raw = Path(args.pio_libs).expanduser().resolve()
        candidates.extend([raw, raw / "esp32-arduino-libs/esp32s3", raw / "esp32s3"])
    home = Path.home()
    candidates.extend([
        home / ".platformio/packages/framework-arduinoespressif32-libs/esp32s3",
        home / ".platformio/packages/framework-arduinoespressif32-libs/esp32-arduino-libs/esp32s3",
        Path("/home/runner/.platformio/packages/framework-arduinoespressif32-libs/esp32s3"),
        Path("/home/runner/.platformio/packages/framework-arduinoespressif32-libs/esp32-arduino-libs/esp32s3"),
    ])
    for c in candidates:
        if c.exists() and (c / "include").exists():
            pio_libs = c
            break

    if pio_libs and pio_libs.exists():
        print(f"Using ESP32-S3 framework headers from: {pio_libs}")
        includes.extend([
            f"-I{pio_libs}/qio_qspi/include",
            f"-I{pio_libs}/include/freertos",
            f"-I{pio_libs}/include/freertos/config/include",
            f"-I{pio_libs}/include/freertos/config/include/freertos",
            f"-I{pio_libs}/include/freertos/config/xtensa/include",
            f"-I{pio_libs}/include/freertos/config/xtensa/include/freertos",
            f"-I{pio_libs}/include/freertos/FreeRTOS-Kernel/include",
            f"-I{pio_libs}/include/freertos/FreeRTOS-Kernel/include/freertos",
            f"-I{pio_libs}/include/freertos/FreeRTOS-Kernel/portable/xtensa/include",
            f"-I{pio_libs}/include/freertos/FreeRTOS-Kernel/portable/xtensa/include/freertos",
            f"-I{pio_libs}/include/freertos/esp_additions/include",
            f"-I{pio_libs}/include/freertos/esp_additions/include/freertos",
            f"-I{pio_libs}/include/xtensa/include",
            f"-I{pio_libs}/include/xtensa/esp32s3/include",
            f"-I{pio_libs}/include/soc/include",
            f"-I{pio_libs}/include/soc/esp32s3/include",
            f"-I{pio_libs}/include/soc/esp32s3/register",
            f"-I{pio_libs}/include/soc/esp32s3",
            f"-I{pio_libs}/include/hal/include",
            f"-I{pio_libs}/include/hal/platform_port/include",
            f"-I{pio_libs}/include/hal/esp32s3/include",
            f"-I{pio_libs}/include/newlib/platform_include",
            f"-I{pio_libs}/include/esp_common/include",
            f"-I{pio_libs}/include/esp_system/include",
            f"-I{pio_libs}/include/esp_hw_support/include",
            f"-I{pio_libs}/include/esp_rom/include",
            f"-I{pio_libs}/include/esp_rom/esp32s3/include",
            f"-I{pio_libs}/include/log/include",
            f"-I{pio_libs}/include/heap/include",
            f"-I{pio_libs}/include/esp_timer/include",
        ])
    else:
        print("ERROR: ESP32-S3 framework headers directory not found!")
        print(f"args.pio_libs={args.pio_libs}")
        print(f"Path.home()={Path.home()}")
        sys.exit(1)

    catalog_apps = []

    for app in config.get("apps", []):
        app_id = app["id"]
        if args.app and app_id != args.app:
            continue
        print(f"\n==========================================")
        print(f"Building {app['name']} ({app_id})...")
        print(f"==========================================")

        repo_url = app["repository"]
        app_repo_dir = cache_dir / app_id
        if not app_repo_dir.exists():
            run_cmd(["git", "clone", "--depth", "1", repo_url, str(app_repo_dir)])
        else:
            run_cmd(["git", "pull", "--ff-only"], cwd=str(app_repo_dir), check=False)

        source_dir = app_repo_dir / app.get("subpath", "")
        app_build_dir = cache_dir / f"build_{app_id}"
        app_build_dir.mkdir(parents=True, exist_ok=True)

        # Compile C sources
        obj_files = []
        c_flags = [
            "-include", str(project_root / "tools/fap_zeroed_heap.h"),
            "-D_GNU_SOURCE",
            "-fno-common",
            "-ffunction-sections",
            "-fdata-sections",
            "-fno-builtin",
            "-fno-jump-tables",
            "-fno-tree-switch-conversion",
            "-std=gnu17",
            "-Os",
            "-g",
            "-DESP_PLATFORM",
            "-mlongcalls",
            "-mtext-section-literals",
            f"-DFAP_VERSION=\"{app.get('version', '1.0')}\"",
            "-DBOARD_INCLUDE=\"board_lilygo_t_embed_cc1101.h\"",
            f"-I{source_dir}",
        ] + includes

        sources = app.get("sources", [])
        if not sources:
            # Auto-detect .c files
            sources = [p.name for p in source_dir.glob("*.c")]

        for src in sources:
            src_path = source_dir / src
            obj_path = app_build_dir / f"{src}.o"
            print(f"Compiling {src}...")
            cmd = [CC] + c_flags + ["-c", str(src_path), "-o", str(obj_path)]
            run_cmd(cmd)
            obj_files.append(str(obj_path))

        # Compatibility shims
        for shim in app.get("compat_shims", []):
            shim_src = project_root / f"tools/compat/{shim}.c"
            if shim_src.exists():
                shim_obj = app_build_dir / f"compat_{shim}.o"
                print(f"Compiling compat shim: {shim}...")
                run_cmd([CC, "-std=gnu17", "-Os", "-DESP_PLATFORM", "-mlongcalls", "-mtext-section-literals"] + includes + ["-c", str(shim_src), "-o", str(shim_obj)])
                obj_files.append(str(shim_obj))

        # Link relocatable ELF
        print("Linking relocatable ELF...")
        elf_path = app_build_dir / "app.elf"
        entry = app.get("entry_point", f"{app_id}_app")
        link_cmd = [LD, "-r", "-T", str(project_root / "tools/fap.ld"), f"--entry={entry}", "-o", str(elf_path)] + obj_files
        run_cmd(link_cmd)

        # Create Manifest
        icon_file = source_dir / app.get("icon", "icon.png")
        manifest_bin = app_build_dir / "manifest.bin"
        manifest_cmd = [
            "python3", str(project_root / "tools/fap_manifest.py"),
            "--name", app["name"],
            "--api-major", "1",
            "--api-minor", "0",
            "--target", "32",
            "--stack-size", str(app.get("stack_size", 16384)),
            "--app-version", "1",
            "--output", str(manifest_bin)
        ]
        if icon_file.exists():
            manifest_cmd.extend(["--icon", str(icon_file)])
            # Copy icon to dist/icons
            shutil.copyfile(icon_file, icons_dir / f"{app_id}.png")

        run_cmd(manifest_cmd)

        # Inject .fapmeta and produce .fap
        final_fap = builds_dir / f"{app_id}.fap"
        objcopy_cmd = [
            OBJCOPY,
            f"--add-section=.fapmeta={manifest_bin}",
            "--set-section-flags", ".fapmeta=contents,readonly",
            "--strip-debug",
            str(elf_path),
            str(final_fap)
        ]
        run_cmd(objcopy_cmd)

        # Symbol validation
        undef_syms_file = app_build_dir / "undef_syms.txt"
        nm_res = run_cmd(f"{NM} -u {final_fap} 2>/dev/null | awk '$1 == \"U\" {{print $2}}' | sort -u > {undef_syms_file}", shell=True, check=False)
        fw_api = fw_dir / "components/flipper_application/flipper_application/firmware_api.c"
        if fw_api.exists():
            check_res = run_cmd(["python3", str(project_root / "tools/check_fap_symbols.py"), str(fw_api), str(undef_syms_file)], check=False)
            print(check_res.stdout)

        print(f"✓ Built {app_id}.fap successfully ({os.path.getsize(final_fap)} bytes)")

        catalog_apps.append({
            "id": app_id,
            "name": app["name"],
            "category": app.get("category", "tools"),
            "author": app.get("author", "Unknown"),
            "description": app.get("description", ""),
            "version": app.get("version", "1.0"),
            "fap_file": f"{app_id}.fap",
            "icon_file": f"{app_id}.png" if icon_file.exists() else None,
            "target": 32,
            "api_version": "1.0",
        })

    # Write catalog index
    catalog_path = out_dir / "catalog.json"
    with open(catalog_path, "w", encoding="utf-8") as f:
        json.dump({
            "categories": config.get("categories", []),
            "applications": catalog_apps
        }, f, indent=2, ensure_ascii=False)
    print(f"\n✓ Generated catalog with {len(catalog_apps)} apps at {catalog_path}")

if __name__ == "__main__":
    main()
