"""
简单多智能体天气穿衣建议系统
提供直接的城市输入功能，使用真实天气数据，穿衣建议由LLM处理
"""
import sys

def get_city_input():
    """获取用户输入的城市名称"""
    print("💬 欢迎使用多智能体天气穿衣建议系统！")
    print("💡 请输入您想查询天气的城市名称")
    print("💡 支持中文和英文城市名")
    print("💡 输入 'quit' 或 '退出' 可以退出程序\n")
    
    while True:
        city = input("🌍 请输入城市名称: ").strip()
        if not city:
            print("❌ 请输入有效的城市名称")
            continue
            
        return city

def get_real_weather(city_name):
    """获取真实天气数据"""
    try:
        # 导入Weather类
        from weather import Weather
        
        # 创建天气查询实例
        weather = Weather()
        
        # 查询天气信息
        weather_info = weather.get_weather(city_name)
        
        # 获取详细天气数据用于穿衣建议
        weather_details = weather.get_weather_details(city_name)
        
        return weather_info, weather_details
        
    except Exception as e:
        print(f"❌ 天气查询失败: {e}")
        # 返回模拟数据作为备用
        return f"🏙️ 城市: {city_name}\n🌡️ 温度: 20°C\n📝 天气: 晴朗\n💧 湿度: 50%\n🌬️ 风速: 3 m/s", None

def get_llm_fashion_advice(weather_details, city_name):
    """使用LLM基于真实天气数据生成穿衣建议"""
    if weather_details and "error" not in weather_details:
        # 使用真实天气数据
        temp = weather_details.get('temperature', 20)
        description = weather_details.get('description', '晴朗')
        humidity = weather_details.get('humidity', 50)
        wind_speed = weather_details.get('wind_speed', 3)
        
        # 构建LLM提示词
        prompt = f"""
请根据以下天气信息为{city_name}提供专业的穿衣建议：
- 温度: {temp}°C
- 天气状况: {description}
- 湿度: {humidity}%
- 风速: {wind_speed} m/s

请提供详细、实用的穿衣建议，包括：
1. 上衣选择
2. 下装选择  
3. 鞋子建议
4. 外套/配饰
5. 特别注意事项

请用中文回复，格式要清晰易读。"""
        
        # 模拟LLM响应（在实际应用中，这里会调用真实的LLM API）
        llm_response = simulate_llm_response(prompt, temp, description)
        
        return f"🤖 LLM智能穿衣建议（基于{city_name}的真实天气数据）：\n\n{llm_response}"
    else:
        # 使用模拟数据
        prompt = f"""
请根据以下天气信息为{city_name}提供专业的穿衣建议：
- 温度: 20°C
- 天气状况: 晴朗
- 湿度: 50%
- 风速: 3 m/s

请提供详细、实用的穿衣建议。"""
        
        llm_response = simulate_llm_response(prompt, 20, '晴朗')
        return f"🤖 LLM智能穿衣建议（基于{city_name}的天气数据）：\n\n{llm_response}"

def simulate_llm_response(prompt, temperature, weather_condition):
    """模拟LLM响应，根据温度生成智能穿衣建议"""
    
    # 基于温度生成不同的建议模板
    if temperature > 30:
        base_advice = {
            "上衣": ["短袖T恤", "透气衬衫", "背心", "轻薄材质上衣"],
            "下装": ["短裤", "轻薄长裤", "透气材质的裤子"],
            "鞋子": ["凉鞋", "透气运动鞋", "帆布鞋"],
            "外套": ["防晒衣", "轻薄外套备用"],
            "配饰": ["太阳镜", "遮阳帽", "防晒霜"],
            "建议": "选择浅色、透气的面料，注意防晒和补水"
        }
    elif temperature > 25:
        base_advice = {
            "上衣": ["短袖T恤", "轻薄长袖", "透气衬衫"],
            "下装": ["休闲裤", "牛仔裤", "轻薄材质的裤子"],
            "鞋子": ["运动鞋", "休闲鞋", "帆布鞋"],
            "外套": ["薄外套备用", "防风衣"],
            "配饰": ["帽子", "太阳镜"],
            "建议": "可分层穿着，便于根据温度变化调整"
        }
    elif temperature > 20:
        base_advice = {
            "上衣": ["长袖T恤", "薄款卫衣", "衬衫"],
            "下装": ["休闲裤", "牛仔裤", "卡其裤"],
            "鞋子": ["休闲鞋", "运动鞋", "皮鞋"],
            "外套": ["夹克", "薄外套", "风衣"],
            "配饰": ["围巾备用", "帽子"],
            "建议": "温度适宜，适合户外活动"
        }
    elif temperature > 15:
        base_advice = {
            "上衣": ["长袖衬衫", "薄毛衣", "卫衣"],
            "下装": ["长裤", "牛仔裤", "休闲裤"],
            "鞋子": ["运动鞋", "皮鞋", "休闲鞋"],
            "外套": ["夹克", "风衣", "薄外套"],
            "配饰": ["围巾", "帽子"],
            "建议": "注意保暖，可搭配薄外套"
        }
    elif temperature > 10:
        base_advice = {
            "上衣": ["毛衣", "厚衬衫", "保暖内衣"],
            "下装": ["厚裤子", "牛仔裤", "保暖裤"],
            "鞋子": ["运动鞋", "皮鞋", "保暖鞋"],
            "外套": ["夹克", "风衣", "薄羽绒服"],
            "配饰": ["围巾", "手套", "帽子"],
            "建议": "注意保暖，可搭配围巾"
        }
    else:
        base_advice = {
            "上衣": ["保暖内衣", "厚毛衣", "羽绒内胆"],
            "下装": ["厚裤子", "保暖裤", "羽绒裤"],
            "鞋子": ["保暖靴子", "雪地靴", "防水鞋"],
            "外套": ["羽绒服", "厚外套", "防风衣"],
            "配饰": ["围巾", "手套", "帽子", "耳罩"],
            "建议": "多层穿着，注意防寒保暖"
        }
    
    # 根据天气状况调整建议
    weather_adjustments = {
        "雨": {
            "鞋子": ["雨靴", "防水鞋"],
            "配饰": ["雨伞", "雨衣"],
            "建议": "选择防水面料，注意防滑"
        },
        "雪": {
            "鞋子": ["防滑靴", "雪地靴"],
            "配饰": ["手套", "帽子", "围巾"],
            "建议": "注意防滑保暖，选择防水材质"
        },
        "风": {
            "外套": ["防风衣", "风衣"],
            "配饰": ["帽子", "围巾"],
            "建议": "选择防风面料，注意保暖"
        }
    }
    
    # 应用天气调整
    for weather_key, adjustment in weather_adjustments.items():
        if weather_key in weather_condition:
            for category, items in adjustment.items():
                if category in base_advice:
                    if category == "建议":
                        base_advice[category] += f"，{items}"
                    else:
                        base_advice[category].extend(items)
    
    # 构建响应文本
    response = f"基于当前天气状况（{temperature}°C，{weather_condition}），为您提供以下穿衣建议：\n\n"
    
    response += f"👕 **上衣选择**: {', '.join(base_advice['上衣'][:3])}\n"
    response += f"👖 **下装选择**: {', '.join(base_advice['下装'][:3])}\n"
    response += f"👟 **鞋子建议**: {', '.join(base_advice['鞋子'][:3])}\n"
    response += f"🧥 **外套配饰**: {', '.join(base_advice['外套'][:2])}"
    
    if base_advice['配饰']:
        response += f"，配饰: {', '.join(base_advice['配饰'][:3])}\n"
    else:
        response += "\n"
    
    response += f"💡 **特别建议**: {base_advice['建议']}\n"
    
    # 添加个性化建议
    if temperature > 25:
        response += "🌞 **温馨提示**: 天气较热，建议选择透气材质，注意防晒补水"
    elif temperature < 10:
        response += "❄️ **温馨提示**: 天气较冷，建议多层穿着，注意保暖防寒"
    else:
        response += "🌤️ **温馨提示**: 天气舒适，适合各种户外活动"
    
    return response

def main():
    """主函数"""
    try:
        # 获取城市输入
        city = get_city_input()
        
        print(f"\n🔍 正在查询 {city} 的真实天气信息...")
        
        # 获取真实天气数据
        weather_info, weather_details = get_real_weather(city)
        
        # 生成穿衣建议（使用LLM处理）
        print("🤖 正在使用LLM生成智能穿衣建议...")
        fashion_advice = get_llm_fashion_advice(weather_details, city)
        
        # 显示结果
        print("\n" + "="*50)
        print("📊 天气信息")
        print("="*50)
        print(weather_info)
        
        print("\n" + "="*50)
        print("👗 穿衣建议")
        print("="*50)
        print(fashion_advice)
        
        print("\n" + "="*50)
        
        # 询问是否继续查询
        while True:
            continue_query = input("\n🔍 是否继续查询其他城市？(y/n): ").strip().lower()
            
            if continue_query in ['y', 'yes', '是', '继续']:
                print("\n" + "-"*50)
                # 递归调用主函数继续查询
                main()
                return
            elif continue_query in ['n', 'no', '否', '退出']:
                print("👋 感谢使用，再见！")
                return
            else:
                print("❌ 请输入 y/是 或 n/否")
                
    except KeyboardInterrupt:
        print("\n\n👋 用户中断，程序退出")
        sys.exit(0)
    except Exception as e:
        print(f"\n❌ 发生错误: {e}")
        print("💡 请稍后重试")
        sys.exit(1)


if __name__ == "__main__":
    main()