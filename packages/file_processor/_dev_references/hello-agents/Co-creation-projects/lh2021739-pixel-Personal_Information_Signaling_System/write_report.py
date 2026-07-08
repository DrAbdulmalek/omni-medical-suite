"""
报告编写工具 - 创建日报/周报/月报
支持交互式输入，保存为Markdown格式
"""

import sys
from pathlib import Path
from datetime import datetime

# 设置控制台编码为UTF-8（Windows）
if sys.platform == 'win32':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')


def get_week_number(date=None):
    """获取ISO周数"""
    if date is None:
        date = datetime.now()
    year, week, _ = date.isocalendar()
    return f"{year}-W{week:02d}"


def get_current_date_id(report_type):
    """获取当前日期标识"""
    now = datetime.now()
    
    if report_type == "daily":
        return now.strftime("%Y-%m-%d")
    elif report_type == "weekly":
        return get_week_number(now)
    elif report_type == "monthly":
        return now.strftime("%Y-%m")
    else:
        return now.strftime("%Y-%m-%d")


def get_report_dir(base_dir, report_type):
    """获取报告目录路径"""
    report_dir = base_dir / "archive" / "reports" / report_type
    report_dir.mkdir(parents=True, exist_ok=True)
    return report_dir


def input_multiline(prompt="请输入报告内容（输入空行后按Enter结束）:\n"):
    """多行输入，以空行结束"""
    print(prompt)
    lines = []
    empty_line_count = 0
    
    while True:
        try:
            line = input()
            if line.strip() == "":
                empty_line_count += 1
                if empty_line_count >= 1:  # 一个空行就结束
                    break
            else:
                empty_line_count = 0
                lines.append(line)
        except EOFError:
            break
        except KeyboardInterrupt:
            print("\n\n⚠️  输入已取消")
            return None
    
    return "\n".join(lines) if lines else None


def save_report(report_dir, date_id, content, report_type):
    """保存报告到文件"""
    file_path = report_dir / f"{date_id}.md"
    
    # 如果文件已存在，询问是否覆盖
    if file_path.exists():
        response = input(f"⚠️  文件 {file_path.name} 已存在，是否覆盖？(y/n): ").strip().lower()
        if response not in ['y', 'yes', '是']:
            print("❌ 已取消保存")
            return False
    
    try:
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(content)
        print(f"✅ 报告已保存到: {file_path}")
        return True
    except Exception as e:
        print(f"❌ 保存失败: {e}")
        return False


def create_report(report_type, base_dir):
    """创建报告"""
    print("=" * 70)
    print(f"创建{report_type}报告")
    print("=" * 70)
    
    # 获取日期标识
    date_id = get_current_date_id(report_type)
    print(f"日期标识: {date_id}")
    
    # 获取报告目录
    report_dir = get_report_dir(base_dir, report_type)
    
    # 检查是否已存在
    existing_file = report_dir / f"{date_id}.md"
    if existing_file.exists():
        print(f"📄 发现已有报告: {existing_file.name}")
        view = input("是否查看现有内容？(y/n): ").strip().lower()
        if view in ['y', 'yes', '是']:
            try:
                with open(existing_file, 'r', encoding='utf-8') as f:
                    print("\n" + "=" * 70)
                    print("现有内容:")
                    print("=" * 70)
                    print(f.read())
                    print("=" * 70)
            except Exception as e:
                print(f"⚠️  读取失败: {e}")
        
        edit = input("\n是否编辑/覆盖？(y/n): ").strip().lower()
        if edit not in ['y', 'yes', '是']:
            print("❌ 已取消")
            return
    
    # 输入报告内容
    print(f"\n请开始输入{report_type}报告内容...")
    print("提示：输入空行后按Enter结束输入")
    content = input_multiline()
    
    if content is None or content.strip() == "":
        print("❌ 内容为空，已取消保存")
        return
    
    # 添加日期标记（可选）
    header = f"# {report_type}报告 - {date_id}\n\n"
    full_content = header + content
    
    # 保存文件
    save_report(report_dir, date_id, full_content, report_type)


def list_reports(base_dir, report_type):
    """列出已有报告"""
    report_dir = get_report_dir(base_dir, report_type)
    
    if not report_dir.exists():
        print(f"📁 目录不存在: {report_dir}")
        return
    
    reports = sorted(report_dir.glob("*.md"))
    
    if not reports:
        print(f"📁 暂无{report_type}报告")
        return
    
    print(f"\n📋 {report_type}报告列表 ({len(reports)}个):")
    print("-" * 70)
    for report in reports:
        size = report.stat().st_size
        mtime = datetime.fromtimestamp(report.stat().st_mtime).strftime("%Y-%m-%d %H:%M")
        print(f"  {report.name:20s}  {size:6d} 字节  {mtime}")
    print("-" * 70)


def view_report(base_dir, report_type, date_id=None):
    """查看报告内容"""
    if date_id is None:
        date_id = get_current_date_id(report_type)
    
    report_dir = get_report_dir(base_dir, report_type)
    file_path = report_dir / f"{date_id}.md"
    
    if not file_path.exists():
        print(f"❌ 报告不存在: {file_path}")
        return
    
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        print("\n" + "=" * 70)
        print(f"{report_type}报告 - {date_id}")
        print("=" * 70)
        print(content)
        print("=" * 70)
    except Exception as e:
        print(f"❌ 读取失败: {e}")


def main():
    """主函数"""
    import sys
    
    base_dir = Path(__file__).parent
    
    # 检查命令行参数，支持直接启动日报模式
    if len(sys.argv) > 1 and sys.argv[1] in ['--daily', '--auto-daily']:
        create_report("daily", base_dir)
        return
    
    print("=" * 70)
    print("报告编写工具")
    print("=" * 70)
    print("\n请选择操作：")
    print("  1. 创建日报")
    print("  2. 创建周报")
    print("  3. 创建月报")
    print("  4. 查看日报列表")
    print("  5. 查看周报列表")
    print("  6. 查看月报列表")
    print("  7. 查看报告内容")
    print("  0. 退出")
    
    while True:
        choice = input("\n请选择 (0-7): ").strip()
        
        if choice == "0":
            print("👋 再见！")
            break
        elif choice == "1":
            create_report("daily", base_dir)
        elif choice == "2":
            create_report("weekly", base_dir)
        elif choice == "3":
            create_report("monthly", base_dir)
        elif choice == "4":
            list_reports(base_dir, "daily")
        elif choice == "5":
            list_reports(base_dir, "weekly")
        elif choice == "6":
            list_reports(base_dir, "monthly")
        elif choice == "7":
            print("\n请选择报告类型：")
            print("  1. 日报")
            print("  2. 周报")
            print("  3. 月报")
            type_choice = input("选择 (1-3): ").strip()
            if type_choice == "1":
                date_id = input("请输入日期 (YYYY-MM-DD，直接Enter使用今天): ").strip()
                view_report(base_dir, "daily", date_id if date_id else None)
            elif type_choice == "2":
                date_id = input("请输入周标识 (YYYY-Www，直接Enter使用当前周): ").strip()
                view_report(base_dir, "weekly", date_id if date_id else None)
            elif type_choice == "3":
                date_id = input("请输入月份 (YYYY-MM，直接Enter使用当前月): ").strip()
                view_report(base_dir, "monthly", date_id if date_id else None)
        else:
            print("⚠️  无效选择，请重试")


if __name__ == "__main__":
    main()

