# create_knowledge_base.py
import pandas as pd
import os

def create_sample_knowledge_base():
    """创建示例知识库Excel文件"""
    
    # 示例面试问题和答案
    sample_data = [
        {
            "question": "请做个自我介绍",
            "answer": "您好，我是[姓名]，毕业于[学校][专业]。我有[X年]的[相关经验]，熟练掌握[技能1、技能2]等技术。在之前的工作中，我主要负责[具体工作内容]，取得了[具体成果]。我对这个职位很感兴趣，希望能为贵公司贡献我的专业技能。"
        },
        {
            "question": "你为什么想加入我们公司",
            "answer": "我非常认同贵公司的企业文化和发展理念。通过了解，我发现贵公司在[行业/技术]方面有很强的实力，这与我的职业发展目标高度契合。我相信我的[技能/经验]能够为公司创造价值，同时我也能在这里得到更好的发展。"
        },
        {
            "question": "你最大的优点是什么",
            "answer": "我认为我最大的优点是学习能力强和责任心强。例如，在之前的项目中，我主动学习了新技术[具体技术]，不仅按时完成了任务，还帮助团队提升了整体效率。我对自己负责的工作会全力以赴，确保质量和进度。"
        },
        {
            "question": "你最大的缺点是什么",
            "answer": "我有时候对细节过于关注，可能会在某些环节花费较多时间。不过我正在改进这个问题，学会在保证质量的前提下提高效率，合理分配时间和精力。"
        },
        {
            "question": "你有什么问题要问我们的吗",
            "answer": "我想了解一下这个职位的具体工作内容和团队构成。另外，贵公司对新员工有什么培训计划吗？公司未来的发展规划是怎样的？"
        },
        {
            "question": "你的职业规划是什么",
            "answer": "短期内，我希望能快速融入团队，胜任当前职位的工作要求，并在实践中不断提升专业技能。中长期来看，我希望能成为技术专家或团队负责人，为公司承担更多责任，实现个人价值与公司发展的共赢。"
        },
        {
            "question": "你如何处理工作压力",
            "answer": "我认为适度的压力是动力的来源。当面临压力时，我会首先分析问题的根源，制定合理的解决方案和时间计划。同时保持积极的心态，必要时与同事沟通协作。工作之余，我也会通过运动、阅读等方式来放松调节。"
        },
        {
            "question": "你期望的薪资是多少",
            "answer": "我希望薪资能与我的能力和贡献相匹配。我了解到这个职位的市场薪资范围，我相信贵公司会给出公平合理的待遇。我更看重的是这个平台能带给我的成长机会和发展前景。"
        },
        {
            "question": "你会选择我们还是其他公司",
            "answer": "贵公司是我的首选。通过面试和了解，我发现这里的工作环境、团队氛围和发展机会都很符合我的期望。我希望能加入这个团队，与大家一起成长进步。"
        },
        {
            "question": "你有什么兴趣爱好",
            "answer": "我平时喜欢[具体爱好，如阅读、运动、编程等]。这些爱好帮助我保持工作生活平衡，也培养了我的[相关品质，如耐心、团队合作精神等]。"
        },
        {
            "question": "描述一次你解决困难问题的经历",
            "answer": "在之前的项目中，我们遇到了[具体问题]。我首先分析了问题的根本原因，然后制定了解决方案，包括[具体步骤]。通过与团队密切合作，我们最终成功解决了问题，项目按时交付，还得到了客户的高度认可。"
        },
        {
            "question": "你如何与团队成员合作",
            "answer": "我认为团队合作的关键在于沟通和信任。我会主动与同事分享信息，听取他们的意见和建议。在遇到分歧时，我会以解决问题为导向，寻求共同的目标和利益点。我相信每个人都有自己的优势，团队的力量远大于个人。"
        }
    ]
    
    # 创建DataFrame
    df = pd.DataFrame(sample_data)
    
    # 保存为Excel文件
    filename = "knowledge_base.xlsx"
    df.to_excel(filename, index=False, engine='openpyxl')
    
    print(f"✓ 知识库文件已创建: {filename}")
    print(f"✓ 包含 {len(sample_data)} 个问答对")
    print("\n使用说明:")
    print("1. 打开 knowledge_base.xlsx 文件")
    print("2. 在 'question' 列添加面试问题")
    print("3. 在 'answer' 列添加对应的回答")
    print("4. 保存文件后重启后端服务即可生效")
    
    return filename

def validate_knowledge_base(filename="knowledge_base.xlsx"):
    """验证知识库文件格式"""
    try:
        if not os.path.exists(filename):
            print(f"❌ 文件不存在: {filename}")
            return False
        
        df = pd.read_excel(filename)
        
        # 检查必需的列
        required_columns = ['question', 'answer']
        missing_columns = [col for col in required_columns if col not in df.columns]
        
        if missing_columns:
            print(f"❌ 缺少必需的列: {missing_columns}")
            return False
        
        # 检查数据
        empty_questions = df['question'].isna().sum()
        empty_answers = df['answer'].isna().sum()
        total_rows = len(df)
        
        print(f"✓ 知识库验证通过")
        print(f"✓ 总问题数: {total_rows}")
        print(f"✓ 空问题数: {empty_questions}")
        print(f"✓ 空答案数: {empty_answers}")
        print(f"✓ 有效问答对: {total_rows - max(empty_questions, empty_answers)}")
        
        if empty_questions > 0 or empty_answers > 0:
            print("⚠️  建议清理空白行以提高匹配效果")
        
        return True
        
    except Exception as e:
        print(f"❌ 验证失败: {e}")
        return False

if __name__ == "__main__":
    print("=== 知识库管理工具 ===")
    print("1. 创建示例知识库")
    print("2. 验证现有知识库")
    
    choice = input("请选择操作 (1/2): ").strip()
    
    if choice == "1":
        create_sample_knowledge_base()
    elif choice == "2":
        validate_knowledge_base()
    else:
        print("无效选择")
        
    input("按回车键退出...")