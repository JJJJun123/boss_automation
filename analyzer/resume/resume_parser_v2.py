"""
改进的简历解析器，支持多种文档格式
"""
import os
import re
import logging
from io import BytesIO

# 文档解析库
try:
    import docx
except ImportError:
    docx = None
    
try:
    import PyPDF2
except ImportError:
    PyPDF2 = None
    
try:
    from pdfplumber import PDF
except ImportError:
    PDF = None


class ResumeParserV2:
    """改进的简历文件解析器"""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        
    def parse_uploaded_file(self, file_obj):
        """解析上传的文件对象，返回纯文本内容"""
        filename = file_obj.filename
        file_ext = os.path.splitext(filename)[1].lower()
        
        self.logger.info(f"开始解析文件: {filename}, 类型: {file_ext}")
        
        # 读取文件内容
        file_content = file_obj.read()
        file_obj.seek(0)  # 重置文件指针
        
        try:
            if file_ext == '.pdf':
                return self._parse_pdf_bytes(file_content)
            elif file_ext in ['.docx', '.doc']:
                return self._parse_docx_bytes(file_content)
            elif file_ext == '.txt':
                return self._parse_txt_bytes(file_content)
            else:
                # 尝试作为文本文件处理
                return self._parse_txt_bytes(file_content)
                
        except Exception as e:
            self.logger.error(f"文件解析失败: {e}")
            # 返回错误信息而不是抛出异常
            return f"文件解析失败: {str(e)}"
    
    def _parse_pdf_bytes(self, file_content):
        """解析PDF字节流"""
        text_content = ""
        
        # 优先使用pdfplumber（更准确）
        if PDF:
            try:
                with PDF(BytesIO(file_content)) as pdf:
                    for page in pdf.pages:
                        page_text = page.extract_text()
                        if page_text:
                            text_content += page_text + "\n"
                return text_content.strip()
            except Exception as e:
                self.logger.warning(f"pdfplumber解析失败: {e}")
        
        # 回退到PyPDF2
        if PyPDF2:
            try:
                pdf_reader = PyPDF2.PdfReader(BytesIO(file_content))
                for page in pdf_reader.pages:
                    text = page.extract_text()
                    if text:
                        text_content += text + "\n"
                return text_content.strip()
            except Exception as e:
                self.logger.error(f"PyPDF2解析失败: {e}")
                
        return "PDF解析失败：缺少必要的库"
    
    def _parse_docx_bytes(self, file_content):
        """解析DOCX字节流"""
        if not docx:
            return "DOCX解析失败：缺少python-docx库"
            
        try:
            # 创建内存中的文件对象
            doc_stream = BytesIO(file_content)
            doc = docx.Document(doc_stream)
            
            text_content = ""
            # 提取段落文本
            for paragraph in doc.paragraphs:
                if paragraph.text.strip():
                    text_content += paragraph.text + "\n"
            
            # 提取表格文本
            for table in doc.tables:
                for row in table.rows:
                    row_text = []
                    for cell in row.cells:
                        cell_text = cell.text.strip()
                        if cell_text:
                            row_text.append(cell_text)
                    if row_text:
                        text_content += " | ".join(row_text) + "\n"
                        
            return text_content.strip()
            
        except Exception as e:
            self.logger.error(f"DOCX解析错误: {e}")
            # 如果是doc格式（老版本），尝试其他方法
            if '.doc' in str(e).lower():
                return "暂不支持DOC格式，请转换为DOCX或PDF格式"
            return f"DOCX解析失败: {str(e)}"
    
    def _parse_txt_bytes(self, file_content):
        """解析文本字节流"""
        # 尝试多种编码
        encodings = ['utf-8', 'gbk', 'gb2312', 'utf-16', 'big5']
        
        for encoding in encodings:
            try:
                return file_content.decode(encoding).strip()
            except UnicodeDecodeError:
                continue
                
        # 如果都失败，使用错误处理
        return file_content.decode('utf-8', errors='ignore').strip()
    
    def extract_basic_info(self, text):
        """从文本中提取基本信息"""
        info = {
            'name': '未知',
            'phone': '未提供',
            'email': '未提供',
            'experience_years': 0,
            'education': '未知',
            'current_position': '未知',
            'skills': []
        }
        
        # 提取姓名（优化的正则）
        name_patterns = [
            r'姓\s*名[：:]\s*([^\s\n]+)',
            r'Name[：:]\s*([^\s\n]+)',
            r'^([^\s\n]{2,4})(?:\s|$)',  # 开头的2-4个字
        ]
        
        for pattern in name_patterns:
            match = re.search(pattern, text, re.MULTILINE | re.IGNORECASE)
            if match:
                info['name'] = match.group(1).strip()
                break
        
        # 提取电话
        phone_pattern = r'(?:电话|手机|Tel|Phone|Mobile)[：:\s]*([0-9\-\+\s]{8,20})|(?<!\d)(1[3-9]\d{9})(?!\d)'
        match = re.search(phone_pattern, text, re.IGNORECASE)
        if match:
            info['phone'] = (match.group(1) or match.group(2)).strip()
            # 格式化电话号码
            if len(info['phone']) == 11:
                info['phone'] = f"{info['phone'][:3]}****{info['phone'][7:]}"
        
        # 提取邮箱
        email_pattern = r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'
        match = re.search(email_pattern, text)
        if match:
            info['email'] = match.group(0)
        
        # 提取工作年限
        exp_patterns = [
            r'(\d+)\s*年.*?(?:工作)?经验',
            r'工作.*?(\d+)\s*年',
            r'Experience.*?(\d+)\s*years?',
        ]
        
        for pattern in exp_patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                info['experience_years'] = int(match.group(1))
                break
        
        # 提取学历
        education_levels = {
            '博士': '博士',
            'Ph.D': '博士',
            'PhD': '博士',
            '硕士': '硕士',
            'Master': '硕士',
            '研究生': '硕士',
            '本科': '本科',
            'Bachelor': '本科',
            '学士': '本科',
            '大专': '大专',
            '专科': '大专'
        }
        
        for keyword, level in education_levels.items():
            if keyword.lower() in text.lower():
                info['education'] = level
                break
        
        # 提取当前职位
        position_patterns = [
            r'(?:当前职位|目前职位|Current Position)[：:]\s*([^\n]+)',
            r'职\s*位[：:]\s*([^\n]+)',
            r'Title[：:]\s*([^\n]+)',
        ]
        
        for pattern in position_patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                info['current_position'] = match.group(1).strip()
                break
        
        # 提取技能（扩展技能列表）
        skill_keywords = [
            # 编程语言
            'Python', 'Java', 'JavaScript', 'TypeScript', 'C++', 'C#', 'Go', 'Rust', 'Ruby', 'PHP',
            'R', 'MATLAB', 'Scala', 'Swift', 'Kotlin', 'SQL', 'NoSQL',
            # 框架和工具
            'React', 'Vue', 'Angular', 'Django', 'Flask', 'Spring', 'Node.js', 'Express',
            'TensorFlow', 'PyTorch', 'Keras', 'Scikit-learn', 'Pandas', 'NumPy',
            'Docker', 'Kubernetes', 'Jenkins', 'Git', 'CI/CD',
            # 技能
            '机器学习', '深度学习', '数据分析', '数据挖掘', '风险管理', '量化分析',
            'Machine Learning', 'Deep Learning', 'Data Analysis', 'Risk Management',
            '项目管理', '产品管理', '团队管理', 'Project Management',
            # 金融相关
            '风控', '信贷', '投资', '证券', '基金', '衍生品', '量化交易',
            # 其他
            'Excel', 'PowerPoint', 'Tableau', 'PowerBI', 'SPSS', 'SAS'
        ]
        
        found_skills = []
        text_lower = text.lower()
        for skill in skill_keywords:
            if skill.lower() in text_lower:
                found_skills.append(skill)
        
        info['skills'] = list(set(found_skills))[:15]  # 去重并限制数量
        
        return info