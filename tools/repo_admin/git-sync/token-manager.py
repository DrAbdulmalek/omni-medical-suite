#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
مدير التوكنات الآمن
يخزّن التوكنات في ~/.config/git-sync-system/secrets.env
بصلاحيات 600 (للمستخدم فقط)
Dr. Abdulmalek - Omni Medical Suite
"""
import os
import sys
import stat
import argparse
import json
from pathlib import Path
from getpass import getpass

# ══════════════════════════════════════════════════════════════
#  الإعدادات
# ══════════════════════════════════════════════════════════════

CONFIG_DIR = Path.home() / ".config" / "git-sync-system"
SECRETS_FILE = CONFIG_DIR / "secrets.env"

# التوكنات المدعومة
TOKEN_TYPES = {
    "github": {
        "name": "GitHub Classic Token",
        "prefix": "ghp_",
        "length": 40,
        "help": "https://github.com/settings/tokens",
    },
    "github_vscode": {
        "name": "GitHub VSCode Token",
        "prefix": "ghp_",
        "length": 40,
        "help": "https://github.com/settings/tokens",
    },
    "hf": {
        "name": "HuggingFace Token",
        "prefix": "hf_",
        "help": "https://huggingface.co/settings/tokens",
    },
    "telegram_api_id": {
        "name": "Telegram API ID",
        "prefix": None,
        "numeric": True,
        "help": "https://my.telegram.org",
    },
    "telegram_api_hash": {
        "name": "Telegram API Hash",
        "prefix": None,
        "length": 32,
        "help": "https://my.telegram.org",
    },
    "deepseek": {
        "name": "DeepSeek API Key",
        "prefix": "sk-",
        "length": 32,
        "help": "https://platform.deepseek.com/api_keys",
    },
    "groq": {
        "name": "Groq API Key",
        "prefix": "gsk_",
        "help": "https://console.groq.com/keys",
    },
    "openrouter": {
        "name": "OpenRouter API Key",
        "prefix": "sk-or-",
        "help": "https://openrouter.ai/keys",
    },
    "openai": {
        "name": "OpenAI API Key",
        "prefix": "sk-",
        "help": "https://platform.openai.com/api-keys",
    },
    "zai": {
        "name": "Z.ai API Key",
        "prefix": None,
        "help": "https://z.ai",
    },
    "cursor": {
        "name": "Cursor API Key",
        "prefix": "crsr_",
        "help": "https://cursor.com/settings",
    },
}

# ══════════════════════════════════════════════════════════════
#  الألوان
# ══════════════════════════════════════════════════════════════

class C:
    RED = '\033[91m'
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    BLUE = '\033[94m'
    MAGENTA = '\033[95m'
    CYAN = '\033[96m'
    RESET = '\033[0m'
    BOLD = '\033[1m'

# ══════════════════════════════════════════════════════════════
#  أدوات مساعدة
# ══════════════════════════════════════════════════════════════

def ensure_config_dir():
    """إنشاء مجلد التكوين إن لم يكن موجوداً"""
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    os.chmod(CONFIG_DIR, 0o700)

def load_secrets():
    """تحميل التوكنات من الملف"""
    if not SECRETS_FILE.exists():
        return {}
    
    secrets = {}
    with open(SECRETS_FILE, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith('#'):
                continue
            if '=' in line:
                key, _, value = line.partition('=')
                secrets[key.strip()] = value.strip().strip('"').strip("'")
    return secrets

def save_secrets(secrets):
    """حفظ التوكنات مع صلاحيات آمنة"""
    ensure_config_dir()
    
    with open(SECRETS_FILE, 'w', encoding='utf-8') as f:
        f.write("# ══════════════════════════════════════════════════════════════\n")
        f.write("#  Git Sync System - Secure Token Storage\n")
        f.write("#  WARNING: This file contains secrets - never share it\n")
        f.write("# ══════════════════════════════════════════════════════════════\n\n")
        
        for key, value in sorted(secrets.items()):
            f.write(f"{key}={value}\n")
    
    # صلاحيات 600: المستخدم فقط يقرأ ويكتب
    os.chmod(SECRETS_FILE, stat.S_IRUSR | stat.S_IWUSR)

def mask_token(token, visible=4):
    """إخفاء جزء من التوكن للعرض"""
    if not token or len(token) <= visible * 2:
        return "•" * len(token)
    return token[:visible] + "•" * (len(token) - visible * 2) + token[-visible:]

def validate_token(token_type, value):
    """التحقق من صحة التوكن"""
    spec = TOKEN_TYPES.get(token_type)
    if not spec:
        return True, ""
    
    if spec.get("numeric"):
        if not value.isdigit():
            return False, "يجب أن يكون رقماً فقط"
        return True, ""
    
    if spec.get("prefix") and not value.startswith(spec["prefix"]):
        return False, f"يجب أن يبدأ بـ {spec['prefix']}"
    
    if spec.get("length") and len(value) != spec["length"]:
        return False, f"الطول المتوقع: {spec['length']}، الموجود: {len(value)}"
    
    return True, ""

# ══════════════════════════════════════════════════════════════
#  الأوامر
# ══════════════════════════════════════════════════════════════

def cmd_add(args):
    """إضافة توكن جديد"""
    if args.type not in TOKEN_TYPES:
        print(f"{C.RED}نوع توكن غير معروف: {args.type}{C.RESET}")
        print(f"{C.YELLOW}الأنواع المتاحة:{C.RESET}")
        for t, spec in TOKEN_TYPES.items():
            print(f"  - {t:20} {spec['name']}")
        return 1
    
    spec = TOKEN_TYPES[args.type]
    print(f"\n{C.BOLD}{C.CYAN}+ إضافة: {spec['name']}{C.RESET}")
    print(f"{C.BLUE}المساعدة: {spec['help']}{C.RESET}\n")
    
    # قراءة التوكن
    if args.value:
        token = args.value
    else:
        token = getpass("أدخل التوكن (لن يظهر على الشاشة): ")
    
    token = token.strip()
    if not token:
        print(f"{C.RED}التوكن فارغ{C.RESET}")
        return 1
    
    # التحقق
    valid, err = validate_token(args.type, token)
    if not valid:
        print(f"{C.YELLOW}تحذير: {err}{C.RESET}")
        if not args.force:
            confirm = input("هل تريد المتابعة؟ (y/N): ").strip().lower()
            if confirm != 'y':
                return 1
    
    # الحفظ
    secrets = load_secrets()
    env_key = f"{args.type.upper()}_TOKEN" if not args.type.startswith("telegram") else f"{args.type.upper()}"
    secrets[env_key] = token
    save_secrets(secrets)
    
    print(f"\n{C.GREEN}تم حفظ {spec['name']}{C.RESET}")
    print(f"{C.BLUE}الموقع: {SECRETS_FILE}{C.RESET}")
    print(f"{C.BLUE}الصلاحيات: 600 (للمستخدم فقط){C.RESET}")
    return 0

def cmd_list(args):
    """عرض التوكنات المحفوظة"""
    secrets = load_secrets()
    
    if not secrets:
        print(f"{C.YELLOW}لا توجد توكنات محفوظة{C.RESET}")
        print(f"{C.BLUE}استخدم: token-manager add <type>{C.RESET}")
        return 0
    
    print(f"\n{C.BOLD}{C.CYAN}التوكنات المحفوظة:{C.RESET}")
    print(f"{C.BLUE}الموقع: {SECRETS_FILE}{C.RESET}\n")
    
    print(f"{'النوع':<25} {'القيمة':<30} {'الحالة'}")
    print("-" * 70)
    
    for key, value in sorted(secrets.items()):
        token_type = key.replace("_TOKEN", "").lower()
        spec = TOKEN_TYPES.get(token_type, {"name": token_type})
        name = spec.get("name", token_type)
        
        if args.show:
            display = value
        else:
            display = mask_token(value)
        
        valid, _ = validate_token(token_type, value)
        status = f"{C.GREEN}OK{C.RESET}" if valid else f"{C.YELLOW}?{C.RESET}"
        
        print(f"{name:<25} {display:<30} {status}")
    
    print(f"\n{C.BOLD}الإجمالي: {len(secrets)} توكن{C.RESET}")
    
    if not args.show:
        print(f"\n{C.YELLOW}لعرض القيم الكاملة: token-manager list --show{C.RESET}")
    
    return 0

def cmd_remove(args):
    """حذف توكن"""
    secrets = load_secrets()
    env_key = f"{args.type.upper()}_TOKEN" if not args.type.startswith("telegram") else f"{args.type.upper()}"
    
    if env_key not in secrets:
        print(f"{C.RED}التوكن غير موجود: {args.type}{C.RESET}")
        return 1
    
    if not args.force:
        confirm = input(f"هل تريد حذف {args.type}؟ (y/N): ").strip().lower()
        if confirm != 'y':
            return 0
    
    del secrets[env_key]
    save_secrets(secrets)
    print(f"{C.GREEN}تم حذف {args.type}{C.RESET}")
    return 0

def cmd_export(args):
    """تصدير التوكنات كـ source-able shell"""
    secrets = load_secrets()
    
    if not secrets:
        print(f"{C.YELLOW}لا توجد توكنات{C.RESET}", file=sys.stderr)
        return 1
    
    if args.format == "shell":
        for key, value in sorted(secrets.items()):
            print(f"export {key}=\"{value}\"")
    elif args.format == "json":
        print(json.dumps(secrets, indent=2))
    elif args.format == "env":
        for key, value in sorted(secrets.items()):
            print(f"{key}={value}")
    
    return 0

def cmd_check(args):
    """فحص أمان ملف التوكنات"""
    print(f"\n{C.BOLD}{C.CYAN}فحص الأمان:{C.RESET}\n")
    
    if not SECRETS_FILE.exists():
        print(f"{C.YELLOW}ملف التوكنات غير موجود{C.RESET}")
        print(f"{C.BLUE}سيتم إنشاؤه عند إضافة أول توكن{C.RESET}")
        return 0
    
    # فحص الصلاحيات
    mode = SECRETS_FILE.stat().st_mode
    mode_str = stat.S_IMODE(mode)
    
    if mode_str == 0o600:
        print(f"{C.GREEN}[OK] صلاحيات الملف: 600 (آمن){C.RESET}")
    else:
        print(f"{C.RED}[FAIL] صلاحيات الملف: {oct(mode_str)} (غير آمن!){C.RESET}")
        print(f"{C.YELLOW}للإصلاح: chmod 600 {SECRETS_FILE}{C.RESET}")
    
    # فحص المجلد
    dir_mode = stat.S_IMODE(CONFIG_DIR.stat().st_mode)
    if dir_mode == 0o700:
        print(f"{C.GREEN}[OK] صلاحيات المجلد: 700 (آمن){C.RESET}")
    else:
        print(f"{C.RED}[FAIL] صلاحيات المجلد: {oct(dir_mode)} (غير آمن!){C.RESET}")
    
    # فحص الملكية
    owner = SECRETS_FILE.stat().st_uid
    if owner == os.getuid():
        print(f"{C.GREEN}[OK] الملكية: لك وحدك{C.RESET}")
    else:
        print(f"{C.RED}[FAIL] الملكية: مستخدم آخر{C.RESET}")
    
    # عدد التوكنات
    secrets = load_secrets()
    print(f"\n{C.BLUE}عدد التوكنات المحفوظة: {len(secrets)}{C.RESET}")
    
    return 0

def cmd_import_batch(args):
    """استيراد مجموعة توكنات من ملف"""
    if not os.path.exists(args.file):
        print(f"{C.RED}الملف غير موجود: {args.file}{C.RESET}")
        return 1
    
    secrets = load_secrets()
    added = 0
    
    with open(args.file, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith('#'):
                continue
            if '=' in line:
                key, _, value = line.partition('=')
                key = key.strip()
                value = value.strip().strip('"').strip("'")
                if value:
                    secrets[key] = value
                    added += 1
    
    save_secrets(secrets)
    print(f"{C.GREEN}تم استيراد {added} توكن{C.RESET}")
    return 0

# ══════════════════════════════════════════════════════════════
#  CLI الرئيسي
# ══════════════════════════════════════════════════════════════

def main():
    parser = argparse.ArgumentParser(
        description="مدير التوكنات الآمن - Git Sync System",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
أمثلة:
  token-manager add github              # إضافة GitHub token
  token-manager add hf                  # إضافة HuggingFace token
  token-manager list                    # عرض التوكنات (مخفية)
  token-manager list --show             # عرض التوكنات كاملة
  token-manager remove github           # حذف GitHub token
  token-manager export                  # تصدير كـ shell
  token-manager check                   # فحص الأمان
  token-manager import tokens.txt       # استيراد من ملف

الأنواع المدعومة:
  github, github_vscode, hf, telegram_api_id, telegram_api_hash,
  deepseek, groq, openrouter, openai, zai, cursor
        """
    )
    
    subparsers = parser.add_subparsers(dest="command", help="الأوامر")
    
    # add
    p_add = subparsers.add_parser("add", help="إضافة توكن")
    p_add.add_argument("type", help="نوع التوكن")
    p_add.add_argument("--value", "-v", help="قيمة التوكن (بدلاً من الإدخال التفاعلي)")
    p_add.add_argument("--force", "-f", action="store_true", help="تجاوز التحقق")
    
    # list
    p_list = subparsers.add_parser("list", help="عرض التوكنات")
    p_list.add_argument("--show", "-s", action="store_true", help="عرض القيم الكاملة")
    
    # remove
    p_remove = subparsers.add_parser("remove", help="حذف توكن")
    p_remove.add_argument("type", help="نوع التوكن")
    p_remove.add_argument("--force", "-f", action="store_true", help="بدون تأكيد")
    
    # export
    p_export = subparsers.add_parser("export", help="تصدير التوكنات")
    p_export.add_argument("--format", "-f", choices=["shell", "json", "env"],
                         default="shell", help="صيغة التصدير")
    
    # check
    subparsers.add_parser("check", help="فحص أمان ملف التوكنات")
    
    # import
    p_import = subparsers.add_parser("import", help="استيراد من ملف")
    p_import.add_argument("file", help="مسار الملف")
    
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        return 0
    
    commands = {
        "add": cmd_add,
        "list": cmd_list,
        "remove": cmd_remove,
        "export": cmd_export,
        "check": cmd_check,
        "import": cmd_import_batch,
    }
    
    return commands[args.command](args)

if __name__ == '__main__':
    sys.exit(main())