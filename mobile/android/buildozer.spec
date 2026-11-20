[app]

# ─────────────────────────────────────────────────────────────────────────────
# OmniMedical Suite — Android APK Build Specification (buildozer)
# ─────────────────────────────────────────────────────────────────────────────
# Build:
#     buildozer -v android debug
# Deploy & run on connected device:
#     buildozer android deploy run
# Release (signed) APK:
#     buildozer android release
#
# Requirements: buildozer >= 1.5.0, Python 3.11, Java 17, Android SDK 33,
# Android NDK 25b, Cython 0.29.36 (NOT 3.x — Kivy recipe incompatibility).
# ─────────────────────────────────────────────────────────────────────────────

# (str) Title of your application
title = OmniMedical

# (str) Package name
package.name = omnimedical

# (str) Package domain (needed for android/namespace)
package.domain = com.omnimedical

# (str) Source code directory
source.dir = .

# (list) Source files to include (let buildozer walk from source.dir)
source.include_exts = py,png,jpg,jpeg,ttf,json,onnx,pth,traineddata,md,txt,yaml,yml

# (list) Source files to exclude
source.exclude_exts = spec,sh,bak,swp

# (list) List of directory to exclude when collecting sources
source.exclude_dirs = build, dist, .git, .github, __pycache__, tests, scripts, docs, user_data

# (list) List of exclusions using pattern matching
source.exclude_patterns = *_test.py, *_legacy.py, *_old.py, .gitignore, .DS_Store

# (str) Application versioning
version.regex = __version__ = ['"]([0-9.]+)['"]
version.filename = %(source.dir)s/main.py

# (str) Application version code (bumped manually per release)
version.code = 110

# (list) Application requirements
# comma-separated e.g. requirements = sqlite3,kivy
#
# CRITICAL ORDER:
#   1. python, kivy, kivymd first (core)
#   2. numpy, opencv, pillow (image pipeline)
#   3. onnxruntime (CPU EP only — removes CUDA libs, saves ~80MB)
#   4. pytesseract + tesseract-ocr (recipe)
#   5. huggingface_hub (model download)
#   6. spellchecker, ftfy, regex (post-processing)
#
# Approximate APK size budget (target <150MB):
#   python3          ~12 MB
#   kivy             ~8 MB
#   kivymd           ~3 MB
#   numpy            ~10 MB
#   opencv           ~35 MB (headless build via recipe)
#   pillow           ~3 MB
#   onnxruntime      ~18 MB (CPU-only)
#   tesseract + arabic data ~15 MB
#   bundled models   ~25 MB (TrOCR ONNX + EasyOCR + Tesseract ara)
#   other (regex, ftfy, ...) ~5 MB
#   ────────────────────────
#   total            ~134 MB  ✓ under 150MB
requirements =
    python3==3.11,
    kivy==2.3.0,
    kivymd==1.2.0,
    numpy==1.26.4,
    opencv-python==4.9.0.80,
    pillow==10.2.0,
    onnxruntime==1.17.1,
    pytesseract==0.3.10,
    huggingface_hub==0.20.3,
    ftfy==6.1.3,
    regex==2023.12.25,
    requests==2.31.0,
    urllib3==2.2.1,
    pyyaml==6.0.1,
    packaging==23.2

# (str) Custom environment variables (set on device boot)
android.api = 34
android.minapi = 24
android.sdk = 34
android.ndk = 25b
android.ndk_meta = android-ndk-r25b
android.arch = arm64-v8a
android.archs = arm64-v8a, armeabi-v7a

# (str) Android NDK path (auto-detected; override if needed)
# android.ndk_path = /usr/local/android-ndk-r25b

# (bool) Use python-for-android master (latest fixes)
p4a.branch = master
p4a.source_dir = ~/p4a-source

# (str) python-for-android download url (fork with Kivy recipe fixes)
# p4a.url = https://github.com/kivy/python-for-android/archive/master.zip

# (str) p4a bootstrap (sdl2 — required for Kivy)
p4a.bootstrap = sdl2

# (str) p4a command-line flags
# --use-setup-py: read setup.py of dependencies (better metadata)
# --ignore-setup-py: skip setup.py for some recipes (compatibility)
p4a.arguments = --use-setup-py --copy-libs --private=$(pwd) --add-source=$(pwd)/assets --dist-name=omnimedical --release

# (bool) Indicate if the application should be fullscreen or not
fullscreen = 0

# (str) Presplash / orientation / etc.
orientation = portrait

# (list) List of permissions (Android manifest)
android.permissions =
    INTERNET,
    ACCESS_NETWORK_STATE,
    READ_EXTERNAL_STORAGE,
    WRITE_EXTERNAL_STORAGE,
    CAMERA,
    POST_NOTIFICATIONS,
    FOREGROUND_SERVICE,
    WAKE_LOCK,
    VIBRATE

# (int) Target Android API level (compileSdkVersion)
android.api = 34

# (int) Minimum Android API level (minSdkVersion)
android.minapi = 24

# (str) Android logcat filter
android.logcat_filters = *:S python:D

# (bool) Copy library instead of making a libpymodules (saves APK size, faster)
android.copy_libs = 0

# (str) The Android arch to build for
android.arch = arm64-v8a

# (list) Android entry points — DON'T CHANGE without updating AndroidManifest.tmpl
android.entry_points = main.py

# (str) Application icon
icon.filename = %(source.dir)s/assets/icons/icon.png

# (str) Presplash screen image
presplash.filename = %(source.dir)s/assets/icons/presplash.png

# (str) Presplash background color
presplash.color = #0E7C7B

# (bool) Skip byte compile optimization (speed up dev builds)
no-byte-compile-python = False

# (str) Add a custom XML to AndroidManifest.xml
# android.manifests = %(source.dir)s/AndroidManifest.xml

# (list) Add Java files to the android project
# android.add_src =

# (list) Add Java jars to the android project
# android.add_jars =

# (list) Add native libs (.so) to the android project
# android.add_libs =

# (list) Gradle dependencies — e.g. CameraX, WorkManager
android.gradle_dependencies =
    androidx.camera:camera-core:1.3.1,
    androidx.camera:camera-camera2:1.3.1,
    androidx.camera:camera-lifecycle:1.3.1,
    androidx.camera:camera-view:1.3.1,
    androidx.work:work-runtime:2.9.0,
    com.google.android.material:material:1.11.0

# (list) Add maven repositories
android.gradle_repositories =

# (list) Java8 features (lambda, etc.)
android.add_compile_options = --release

# (str) JNIus — for Android API access (notifications, etc.)
android.jnius = 1

# (str) Meta-data
android.meta_data =
    app_name=OmniMedical,
    app_version=1.1.0

# (bool) AndroidX
android.use_androidx = 1

# (str) Theme — Material 3
android.theme = Material3

# ─────────────────────────────────────────────────────────────────────────────
# Build settings
# ─────────────────────────────────────────────────────────────────────────────

# (bool) Skip rebuilding the python-for-android distribution if already built
android.skip_update = False

# (str) Build directory
build_dir = build

# (str) Binaries output directory
bin_dir = bin

# (str) Cache directory for buildozer
cache_dir = ~/.buildozer/cache

# (bool) Skip cleaning between builds (debug only)
android.debug_skip_clean = False

# (bool) Strip debug symbols from .so files (saves ~30% size)
android.strip = 1

# (bool) Use ccache to speed up C compilation
android.ccache = 1

# (str) Java JDK path (auto-detected; override if needed)
# java.path = /usr/lib/jvm/java-17-openjdk-amd64

# ─────────────────────────────────────────────────────────────────────────────
# Recipes (custom build recipes for specific Python packages)
# ─────────────────────────────────────────────────────────────────────────────

# (list) Custom recipes directories
# these recipes handle onnxruntime, opencv, pytesseract compilation for Android
# we use the bundled recipes in python-for-android, but override opencv
recipes = opencv_python==4.9.0.80

# ─────────────────────────────────────────────────────────────────────────────
# Release signing (only for `buildozer android release`)
# ─────────────────────────────────────────────────────────────────────────────

# (str) Path to release keystore (NOT the debug keystore)
# key.store = ~/.android/omnimedical-release.keystore

# (str) Keystore alias
# key.alias = omnimedical

# (str) Keystore password (use env var in CI: $KEYSTORE_PASS)
# key.store_password = ${KEYSTORE_PASS}

# (str) Alias password
# key.alias_password = ${KEYSTORE_PASS}

# ─────────────────────────────────────────────────────────────────────────────
# Pre/Post build hooks
# ─────────────────────────────────────────────────────────────────────────────

# (str) Run before build (e.g. download models to assets/models/)
# prebuild.href = ./scripts/prebuild.sh

# (str) Run after build (e.g. verify APK size)
# postbuild.href = ./scripts/postbuild.sh

# ─────────────────────────────────────────────────────────────────────────────
# Logging & debug
# ─────────────────────────────────────────────────────────────────────────────

# (str) Log level: 0 (silent), 1 (errors), 2 (info), 3 (debug)
log_level = 2

# (bool) Show full traceback on build errors
show_traceback = 1

# (bool) Print all executed commands (verbose)
debug = 1

# ─────────────────────────────────────────────────────────────────────────────
# Server (optional, for buildozer remote — typically unused)
# ─────────────────────────────────────────────────────────────────────────────

# (str) Server IP
# server.ip =

# (str) Server user
# server.user =

# (str) Server directory
# server.dir =

# (str) Server SSH key
# server.key =

[buildozer]

# (bool) Warn about deprecated options
warn_on_deprecated = 1

# (str) Default profile
profile = debug

# (int) Number of parallel build jobs
jobs = 4
