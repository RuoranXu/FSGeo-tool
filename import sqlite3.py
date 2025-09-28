import sqlite3
import json
import os
import re
from datetime import datetime
import uuid
from typing import List, Dict, Optional, Tuple

class GeometryProblemManager:
    """几何题目管理系统，用于管理几何题目及其相关信息"""
    
    # 定义有效的难度级别和题目类型
    VALID_COMPLEXITY_LEVELS = {'Level 1', 'Level 2', 'Level 3', 'Level 4'}
    DEFAULT_PROBLEM_TYPES = [
        "Multi-view Projection",
        "Composite Solid Structures",
        "Spatial Metric Relations",
        "Planar Unfolding and Configuration",
        "Measurement of Solid Geometric Forms",
        "Solid Geometry Modeling",
        "3D Coordinate and Vector Reasoning"
    ]
    
    def __init__(self, db_name: str = "geometry_problems.db"):
        """初始化数据库连接和表结构"""
        self.conn = sqlite3.connect(db_name)
        self.conn.row_factory = sqlite3.Row  # 启用行工厂，方便获取列名
        self.cursor = self.conn.cursor()
        self._create_tables()
        self._init_problem_types()
        
    def _create_tables(self) -> None:
        """创建数据库表结构"""
        # 主表：存储题目基本信息
        self.cursor.execute('''
        CREATE TABLE IF NOT EXISTS problems (
            problem_id TEXT PRIMARY KEY,
            source TEXT,
            problem_text_cn TEXT NOT NULL,
            problem_text_en TEXT,
            problem_answer TEXT,
            complexity_level TEXT CHECK(complexity_level IN ('Level 1', 'Level 2', 'Level 3', 'Level 4')),
            theorem_seqs TEXT,
            created_at TIMESTAMP NOT NULL,
            updated_at TIMESTAMP NOT NULL
        )
        ''')
        
        # 题目类型表（多对多关系）
        self.cursor.execute('''
        CREATE TABLE IF NOT EXISTS problem_types (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            type_name TEXT UNIQUE NOT NULL
        )
        ''')
        
        # 题目与类型的关联表
        self.cursor.execute('''
        CREATE TABLE IF NOT EXISTS problem_type_mapping (
            problem_id TEXT,
            type_id INTEGER,
            FOREIGN KEY (problem_id) REFERENCES problems(problem_id) ON DELETE CASCADE,
            FOREIGN KEY (type_id) REFERENCES problem_types(id) ON DELETE CASCADE,
            PRIMARY KEY (problem_id, type_id)
        )
        ''')
        
        # 图片表
        self.cursor.execute('''
        CREATE TABLE IF NOT EXISTS problem_images (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            problem_id TEXT,
            image_url TEXT NOT NULL,
            image_type TEXT NOT NULL CHECK(image_type IN ('problem_img', 'annotation_img')),
            FOREIGN KEY (problem_id) REFERENCES problems(problem_id) ON DELETE CASCADE
        )
        ''')
        
        # CDL数据表
        self.cursor.execute('''
        CREATE TABLE IF NOT EXISTS problem_cdls (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            problem_id TEXT,
            cdl_type TEXT NOT NULL CHECK(cdl_type IN ('construction_cdl', 'text_cdl', 'image_cdl', 'goal_cdl')),
            cdl_content TEXT NOT NULL,
            FOREIGN KEY (problem_id) REFERENCES problems(problem_id) ON DELETE CASCADE
        )
        ''')
        
        # 注释表
        self.cursor.execute('''
        CREATE TABLE IF NOT EXISTS problem_annotations (
            problem_id TEXT PRIMARY KEY,
            annotation_text TEXT,
            annotation_img_url TEXT,
            FOREIGN KEY (problem_id) REFERENCES problems(problem_id) ON DELETE CASCADE
        )
        ''')
        
        self.conn.commit()
        
    def _init_problem_types(self) -> None:
        """初始化常见的题目类型"""
        for type_name in self.DEFAULT_PROBLEM_TYPES:
            self.cursor.execute('''
            INSERT OR IGNORE INTO problem_types (type_name) VALUES (?)
            ''', (type_name,))
        self.conn.commit()
    
    def _generate_problem_id(self) -> str:
        """生成新的题目ID，格式为GEO-日期-8位UUID"""
        date_str = datetime.now().strftime("%Y%m%d")
        unique_id = str(uuid.uuid4())[:8].upper()
        return f"GEO-{date_str}-{unique_id}"
    
    def _validate_problem_data(self, problem_data: Dict) -> Tuple[bool, str]:
        """验证题目数据的有效性
        
        Args:
            problem_data: 包含题目信息的字典
            
        Returns:
            验证结果和错误信息，如果验证通过，错误信息为空字符串
        """
        # 检查中文题干是否存在
        if not problem_data.get('problem_text_cn', '').strip():
            return False, "中文题干不能为空"
        
        # 验证难度级别
        complexity = problem_data.get('complexity_level', '').strip()
        if complexity and complexity not in self.VALID_COMPLEXITY_LEVELS:
            return False, f"难度级别必须是以下之一: {', '.join(self.VALID_COMPLEXITY_LEVELS)}"
        
        # 验证题目类型
        problem_types = problem_data.get('problem_type', [])
        if problem_types:
            # 获取所有有效类型
            self.cursor.execute("SELECT type_name FROM problem_types")
            valid_types = {row['type_name'] for row in self.cursor.fetchall()}
            
            for type_name in problem_types:
                if type_name not in valid_types:
                    return False, f"无效的题目类型: {type_name}。有效类型: {', '.join(valid_types)}"
        
        # 验证URL格式
        url_fields = [
            ('problem_img', problem_data.get('problem_img', [])),
            ('annotation_img', [problem_data.get('annotation_img')] if problem_data.get('annotation_img') else [])
        ]
        
        url_pattern = re.compile(r'^https?://\S+$|^/[^\s]+$')
        for field_name, urls in url_fields:
            for url in urls:
                if url and not url_pattern.match(url):
                    return False, f"无效的URL格式: {url} (字段: {field_name})"
        
        return True, ""
    
    def add_problem(self, problem_data: Dict) -> Tuple[Optional[str], str]:
        """添加新题目
        
        Args:
            problem_data: 包含题目信息的字典
            
        Returns:
            新题目的ID和状态信息，如果失败则ID为None
        """
        # 验证数据
        is_valid, error_msg = self._validate_problem_data(problem_data)
        if not is_valid:
            return None, f"添加失败: {error_msg}"
        
        try:
            # 生成题目ID
            problem_id = self._generate_problem_id()
            now = datetime.now().isoformat()
            
            # 插入基本信息
            self.cursor.execute('''
            INSERT INTO problems (
                problem_id, source, problem_text_cn, problem_text_en, 
                problem_answer, complexity_level, theorem_seqs,
                created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                problem_id,
                problem_data.get('source', ''),
                problem_data.get('problem_text_cn', ''),
                problem_data.get('problem_text_en', ''),
                problem_data.get('problem_answer', ''),
                problem_data.get('complexity_level', ''),
                ','.join(problem_data.get('theorem_seqs', [])),
                now,
                now
            ))
            
            # 插入题目类型
            for type_name in problem_data.get('problem_type', []):
                self.cursor.execute('''
                SELECT id FROM problem_types WHERE type_name = ?
                ''', (type_name,))
                result = self.cursor.fetchone()
                if result:
                    type_id = result['id']
                    self.cursor.execute('''
                    INSERT INTO problem_type_mapping (problem_id, type_id) VALUES (?, ?)
                    ''', (problem_id, type_id))
            
            # 插入图片
            for img_url in problem_data.get('problem_img', []):
                self.cursor.execute('''
                INSERT INTO problem_images (problem_id, image_url, image_type) VALUES (?, ?, ?)
                ''', (problem_id, img_url, 'problem_img'))
            
            # 插入注释图片
            if problem_data.get('annotation_img'):
                self.cursor.execute('''
                INSERT INTO problem_images (problem_id, image_url, image_type) VALUES (?, ?, ?)
                ''', (problem_id, problem_data['annotation_img'], 'annotation_img'))
            
            # 插入CDL数据
            cdl_types = ['construction_cdl', 'text_cdl', 'image_cdl', 'goal_cdl']
            for cdl_type in cdl_types:
                if cdl_type in problem_data and problem_data[cdl_type]:
                    if isinstance(problem_data[cdl_type], list):
                        content = '\n'.join(problem_data[cdl_type])
                    else:
                        content = str(problem_data[cdl_type])
                    self.cursor.execute('''
                    INSERT INTO problem_cdls (problem_id, cdl_type, cdl_content) VALUES (?, ?, ?)
                    ''', (problem_id, cdl_type, content))
            
            # 插入注释
            if 'annotation' in problem_data:
                self.cursor.execute('''
                INSERT INTO problem_annotations (problem_id, annotation_text, annotation_img_url) 
                VALUES (?, ?, ?)
                ''', (
                    problem_id,
                    problem_data['annotation'],
                    problem_data.get('annotation_img', '')
                ))
            
            self.conn.commit()
            return problem_id, "题目创建成功"
            
        except Exception as e:
            self.conn.rollback()
            return None, f"添加失败: {str(e)}"
    
    def get_problem(self, problem_id: str) -> Optional[Dict]:
        """获取单个题目详情
        
        Args:
            problem_id: 题目的唯一标识符
            
        Returns:
            包含题目详细信息的字典，如果不存在则返回None
        """
        try:
            # 获取基本信息
            self.cursor.execute('''
            SELECT * FROM problems WHERE problem_id = ?
            ''', (problem_id,))
            problem_row = self.cursor.fetchone()
            if not problem_row:
                return None
            
            # 转换为字典
            problem_dict = dict(problem_row)
            
            # 获取题目类型
            self.cursor.execute('''
            SELECT pt.type_name FROM problem_type_mapping ptm
            JOIN problem_types pt ON ptm.type_id = pt.id
            WHERE ptm.problem_id = ?
            ''', (problem_id,))
            problem_dict['problem_type'] = [row['type_name'] for row in self.cursor.fetchall()]
            
            # 获取题目图片
            self.cursor.execute('''
            SELECT image_url FROM problem_images 
            WHERE problem_id = ? AND image_type = 'problem_img'
            ''', (problem_id,))
            problem_dict['problem_img'] = [row['image_url'] for row in self.cursor.fetchall()]
            
            # 获取CDL数据
            self.cursor.execute('''
            SELECT cdl_type, cdl_content FROM problem_cdls 
            WHERE problem_id = ?
            ''', (problem_id,))
            cdls = self.cursor.fetchall()
            for cdl in cdls:
                problem_dict[cdl['cdl_type']] = cdl['cdl_content'].split('\n')
            
            # 获取注释
            self.cursor.execute('''
            SELECT annotation_text, annotation_img_url FROM problem_annotations 
            WHERE problem_id = ?
            ''', (problem_id,))
            annotation = self.cursor.fetchone()
            if annotation:
                problem_dict['annotation'] = annotation['annotation_text']
                problem_dict['annotation_img'] = annotation['annotation_img_url']
            
            # 处理定理序列
            if problem_dict['theorem_seqs']:
                problem_dict['theorem_seqs'] = [seq.strip() for seq in problem_dict['theorem_seqs'].split(',') if seq.strip()]
            else:
                problem_dict['theorem_seqs'] = []
                
            return problem_dict
            
        except Exception as e:
            print(f"获取题目失败: {str(e)}")
            return None
    
    def search_problems(self, keyword: str, search_fields: List[str] = None) -> List[Dict]:
        """搜索题目
        
        Args:
            keyword: 搜索关键词
            search_fields: 要搜索的字段列表，默认为所有字段
            
        Returns:
            匹配的题目列表
        """
        if not keyword:
            return []
            
        # 默认搜索字段
        default_fields = ['problem_id', 'problem_text_cn', 'problem_text_en', 'source']
        search_fields = search_fields or default_fields
        
        # 验证搜索字段是否有效
        valid_fields = set(default_fields)
        invalid_fields = [f for f in search_fields if f not in valid_fields]
        if invalid_fields:
            print(f"警告: 无效的搜索字段 {invalid_fields}，将使用默认字段")
            search_fields = default_fields
        
        # 构建SQL查询
        keyword = f"%{keyword}%"
        where_clause = " OR ".join([f"{field} LIKE ?" for field in search_fields])
        
        try:
            self.cursor.execute(f'''
            SELECT problem_id, problem_text_cn, problem_text_en, source 
            FROM problems 
            WHERE {where_clause}
            ORDER BY created_at DESC
            ''', [keyword] * len(search_fields))
            
            results = []
            for row in self.cursor.fetchall():
                results.append(dict(row))
                
            return results
            
        except Exception as e:
            print(f"搜索失败: {str(e)}")
            return []
    
    def get_all_problem_ids(self) -> List[str]:
        """获取所有题目ID，按创建时间降序排列"""
        try:
            self.cursor.execute('SELECT problem_id FROM problems ORDER BY created_at DESC')
            return [row['problem_id'] for row in self.cursor.fetchall()]
        except Exception as e:
            print(f"获取题目ID列表失败: {str(e)}")
            return []
    
    def get_problem_types(self) -> List[str]:
        """获取所有可用的题目类型"""
        try:
            self.cursor.execute('SELECT type_name FROM problem_types ORDER BY type_name')
            return [row['type_name'] for row in self.cursor.fetchall()]
        except Exception as e:
            print(f"获取题目类型失败: {str(e)}")
            return []
    
    def update_problem(self, problem_id: str, problem_data: Dict) -> Tuple[bool, str]:
        """更新题目信息
        
        Args:
            problem_id: 要更新的题目的ID
            problem_data: 包含更新信息的字典
            
        Returns:
            更新结果和状态信息
        """
        # 检查题目是否存在
        if not self.get_problem(problem_id):
            return False, f"题目 {problem_id} 不存在"
        
        # 验证数据
        is_valid, error_msg = self._validate_problem_data(problem_data)
        if not is_valid:
            return False, f"更新失败: {error_msg}"
        
        try:
            now = datetime.now().isoformat()
            
            # 更新基本信息
            self.cursor.execute('''
            UPDATE problems SET 
                source = ?, 
                problem_text_cn = ?, 
                problem_text_en = ?, 
                problem_answer = ?, 
                complexity_level = ?, 
                theorem_seqs = ?,
                updated_at = ?
            WHERE problem_id = ?
            ''', (
                problem_data.get('source', ''),
                problem_data.get('problem_text_cn', ''),
                problem_data.get('problem_text_en', ''),
                problem_data.get('problem_answer', ''),
                problem_data.get('complexity_level', ''),
                ','.join(problem_data.get('theorem_seqs', [])),
                now,
                problem_id
            ))
            
            # 更新题目类型（先删除再添加）
            self.cursor.execute('''
            DELETE FROM problem_type_mapping WHERE problem_id = ?
            ''', (problem_id,))
            
            for type_name in problem_data.get('problem_type', []):
                self.cursor.execute('''
                SELECT id FROM problem_types WHERE type_name = ?
                ''', (type_name,))
                result = self.cursor.fetchone()
                if result:
                    type_id = result['id']
                    self.cursor.execute('''
                    INSERT INTO problem_type_mapping (problem_id, type_id) VALUES (?, ?)
                    ''', (problem_id, type_id))
            
            # 更新图片
            self.cursor.execute('''
            DELETE FROM problem_images WHERE problem_id = ? AND image_type = 'problem_img'
            ''', (problem_id,))
            
            for img_url in problem_data.get('problem_img', []):
                self.cursor.execute('''
                INSERT INTO problem_images (problem_id, image_url, image_type) VALUES (?, ?, ?)
                ''', (problem_id, img_url, 'problem_img'))
            
            # 更新注释图片
            self.cursor.execute('''
            DELETE FROM problem_images WHERE problem_id = ? AND image_type = 'annotation_img'
            ''', (problem_id,))
            
            if problem_data.get('annotation_img'):
                self.cursor.execute('''
                INSERT INTO problem_images (problem_id, image_url, image_type) VALUES (?, ?, ?)
                ''', (problem_id, problem_data['annotation_img'], 'annotation_img'))
            
            # 更新CDL数据
            self.cursor.execute('''
            DELETE FROM problem_cdls WHERE problem_id = ?
            ''', (problem_id,))
            
            cdl_types = ['construction_cdl', 'text_cdl', 'image_cdl', 'goal_cdl']
            for cdl_type in cdl_types:
                if cdl_type in problem_data and problem_data[cdl_type]:
                    if isinstance(problem_data[cdl_type], list):
                        content = '\n'.join(problem_data[cdl_type])
                    else:
                        content = str(problem_data[cdl_type])
                    self.cursor.execute('''
                    INSERT INTO problem_cdls (problem_id, cdl_type, cdl_content) VALUES (?, ?, ?)
                    ''', (problem_id, cdl_type, content))
            
            # 更新注释
            self.cursor.execute('''
            DELETE FROM problem_annotations WHERE problem_id = ?
            ''', (problem_id,))
            
            if 'annotation' in problem_data:
                self.cursor.execute('''
                INSERT INTO problem_annotations (problem_id, annotation_text, annotation_img_url) 
                VALUES (?, ?, ?)
                ''', (
                    problem_id,
                    problem_data['annotation'],
                    problem_data.get('annotation_img', '')
                ))
            
            self.conn.commit()
            return True, "题目更新成功"
            
        except Exception as e:
            self.conn.rollback()
            return False, f"更新失败: {str(e)}"
    
    def delete_problem(self, problem_id: str) -> Tuple[bool, str]:
        """删除题目
        
        Args:
            problem_id: 要删除的题目的ID
            
        Returns:
            删除结果和状态信息
        """
        # 检查题目是否存在
        if not self.get_problem(problem_id):
            return False, f"题目 {problem_id} 不存在"
        
        try:
            # 由于设置了ON DELETE CASCADE，只需删除主表记录即可
            self.cursor.execute('DELETE FROM problems WHERE problem_id = ?', (problem_id,))
            self.conn.commit()
            return True, f"题目 {problem_id} 已成功删除"
            
        except Exception as e:
            self.conn.rollback()
            return False, f"删除失败: {str(e)}"
    
    def export_to_json(self, problem_ids: List[str] = None, file_path: str = None) -> Tuple[Optional[str], str]:
        """导出题目到JSON文件
        
        Args:
            problem_ids: 要导出的题目ID列表，默认为所有题目
            file_path: 导出文件路径，默认为自动生成
            
        Returns:
            导出文件路径和状态信息，如果失败则路径为None
        """
        try:
            if not problem_ids:
                problem_ids = self.get_all_problem_ids()
                
            if not problem_ids:
                return None, "没有题目可导出"
                
            problems = []
            for pid in problem_ids:
                problem = self.get_problem(pid)
                if problem:
                    problems.append(problem)
            
            if not file_path:
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                file_path = f"geo_problems_export_{timestamp}.json"
            
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(problems, f, ensure_ascii=False, indent=2)
            
            return file_path, f"成功导出 {len(problems)} 个题目到 {file_path}"
            
        except Exception as e:
            return None, f"导出失败: {str(e)}"
    
    def import_from_json(self, file_path: str) -> Tuple[bool, str]:
        """从JSON文件导入题目
        
        Args:
            file_path: 导入文件路径
            
        Returns:
            导入结果和状态信息
        """
        if not os.path.exists(file_path):
            return False, "文件不存在"
        
        if not os.path.isfile(file_path):
            return False, "指定路径不是一个文件"
        
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                problems = json.load(f)
            
            if not isinstance(problems, list):
                return False, "JSON文件格式不正确，应为题目列表"
            
            imported_count = 0
            updated_count = 0
            failed_count = 0
            
            for problem in problems:
                if not isinstance(problem, dict):
                    failed_count += 1
                    continue
                    
                # 处理题目ID
                if 'problem_id' in problem:
                    existing = self.get_problem(problem['problem_id'])
                    if existing:
                        # 更新现有题目
                        success, _ = self.update_problem(problem['problem_id'], problem)
                        if success:
                            updated_count += 1
                        else:
                            failed_count += 1
                    else:
                        # 添加新题目（忽略原有ID，生成新ID）
                        problem_data = problem.copy()
                        del problem_data['problem_id']
                        pid, _ = self.add_problem(problem_data)
                        if pid:
                            imported_count += 1
                        else:
                            failed_count += 1
                else:
                    # 添加新题目
                    pid, _ = self.add_problem(problem)
                    if pid:
                        imported_count += 1
                    else:
                        failed_count += 1
            
            msg = (f"导入完成。成功导入 {imported_count} 个新题目，"
                  f"更新 {updated_count} 个现有题目，"
                  f"导入失败 {failed_count} 个题目")
            return True, msg
            
        except json.JSONDecodeError:
            return False, "JSON文件格式错误，无法解析"
        except Exception as e:
            return False, f"导入失败: {str(e)}"
    
    def close(self) -> None:
        """关闭数据库连接"""
        self.conn.close()


def main():
    """命令行交互界面"""
    manager = GeometryProblemManager()
    current_problem_id = None
    problem_ids = manager.get_all_problem_ids()
    current_index = 0 if problem_ids else -1
    
    print("===== 几何题目管理系统 =====")
    print("命令列表:")
    print("  n - 新建题目")
    print("  p - 上一题")
    print("  nx - 下一题")  # 修改命令避免与新建冲突
    print("  s [关键词] - 搜索题目")
    print("  v - 查看当前题目")
    print("  e - 导出题目")
    print("  i [文件路径] - 导入题目")
    print("  u - 更新当前题目")
    print("  d - 删除当前题目")
    print("  t - 显示所有题目类型")
    print("  q - 退出系统")
    
    while True:
        cmd = input("\n请输入命令: ").strip().lower()
        
        if cmd == 'q':
            print("谢谢使用，再见！")
            manager.close()
            break
            
        elif cmd == 'n':
            # 新建题目
            print("\n===== 新建几何题目 =====")
            print("提示：带*的为必填项")
            
            new_problem = {
                'source': input("请输入来源: "),
                'problem_text_cn': input("请输入中文题干*: "),
                'problem_text_en': input("请输入英文题干: "),
                'problem_answer': input("请输入答案与解析: "),
                'complexity_level': input(f"请输入难度级别 (可选值: {', '.join(manager.VALID_COMPLEXITY_LEVELS)}): "),
                'theorem_seqs': [seq.strip() for seq in input("请输入定理序列 (用逗号分隔): ").split(',') if seq.strip()]
            }
            
            # 显示可用类型
            print("\n可用题目类型:")
            types = manager.get_problem_types()
            for i, type_name in enumerate(types, 1):
                print(f"  {i}. {type_name}")
            
            type_input = input("请输入题目类型编号 (用逗号分隔，如1,3): ")
            type_indices = [int(idx.strip()) - 1 for idx in type_input.split(',') if idx.strip().isdigit()]
            new_problem['problem_type'] = [types[i] for i in type_indices if 0 <= i < len(types)]
            
            # 添加图片（可选）
            if input("是否添加题目图片? (y/n): ").lower() == 'y':
                img_count = input("请输入图片数量: ")
                if img_count.isdigit() and int(img_count) > 0:
                    new_problem['problem_img'] = [input(f"图片 {i+1} URL: ") for i in range(int(img_count))]
            
            # 添加注释（可选）
            if input("是否添加注释? (y/n): ").lower() == 'y':
                new_problem['annotation'] = input("请输入注释内容: ")
                if input("是否添加注释图片? (y/n): ").lower() == 'y':
                    new_problem['annotation_img'] = input("注释图片URL: ")
            
            # 添加CDL数据（可选）
            if input("是否添加CDL数据? (y/n): ").lower() == 'y':
                cdl_types = ['construction_cdl', 'text_cdl', 'image_cdl', 'goal_cdl']
                for cdl_type in cdl_types:
                    if input(f"是否添加{cdl_type}? (y/n): ").lower() == 'y':
                        lines = []
                        print(f"输入{cdl_type}内容（空行结束）:")
                        while True:
                            line = input()
                            if not line:
                                break
                            lines.append(line)
                        if lines:
                            new_problem[cdl_type] = lines
            
            pid, msg = manager.add_problem(new_problem)
            print(msg)
            if pid:
                problem_ids = manager.get_all_problem_ids()
                current_index = problem_ids.index(pid)
                current_problem_id = pid
                
        elif cmd == 'p':
            # 上一题
            if len(problem_ids) == 0:
                print("没有题目可浏览")
                continue
                
            current_index = (current_index - 1) % len(problem_ids)
            current_problem_id = problem_ids[current_index]
            print(f"当前题目ID: {current_problem_id}")
            print("输入 v 查看题目详情")
            
        elif cmd == 'nx':
            # 下一题（修改命令避免与新建冲突）
            if len(problem_ids) == 0:
                print("没有题目可浏览")
                continue
                
            current_index = (current_index + 1) % len(problem_ids)
            current_problem_id = problem_ids[current_index]
            print(f"当前题目ID: {current_problem_id}")
            print("输入 v 查看题目详情")
            
        elif cmd.startswith('s '):
            # 搜索题目
            keyword = cmd[2:]
            results = manager.search_problems(keyword)
            print(f"找到 {len(results)} 个匹配结果:")
            for i, res in enumerate(results, 1):
                print(f"{i}. {res['problem_id']}")
                print(f"   中文题干: {res['problem_text_cn'][:80]}{'...' if len(res['problem_text_cn'])>80 else ''}")
            
            if results and input("是否跳转到某个题目? (y/n): ").lower() == 'y':
                try:
                    idx = int(input("请输入序号: ")) - 1
                    if 0 <= idx < len(results):
                        current_problem_id = results[idx]['problem_id']
                        current_index = problem_ids.index(current_problem_id)
                        print(f"已切换到题目: {current_problem_id}")
                except ValueError:
                    print("无效的序号")
                
        elif cmd == 'v':
            # 查看当前题目
            if not current_problem_id:
                print("请先选择一个题目")
                continue
                
            problem = manager.get_problem(current_problem_id)
            if not problem:
                print("题目不存在")
                continue
                
            print("\n" + "="*60)
            print(f"题目ID: {problem['problem_id']}")
            print(f"来源: {problem['source'] or '未设置'}")
            print(f"类型: {', '.join(problem['problem_type']) or '未设置'}")
            print(f"难度: {problem['complexity_level'] or '未设置'}")
            print(f"创建时间: {problem['created_at']}")
            if problem['created_at'] != problem['updated_at']:
                print(f"更新时间: {problem['updated_at']}")
            
            print("\n中文题干:")
            print(problem['problem_text_cn'])
            
            if problem['problem_text_en']:
                print("\n英文题干:")
                print(problem['problem_text_en'])
            
            if problem['theorem_seqs']:
                print("\n定理序列:")
                print(", ".join(problem['theorem_seqs']))
            
            if problem['problem_img']:
                print("\n题目图片:")
                for i, img_url in enumerate(problem['problem_img'], 1):
                    print(f"  {i}. {img_url}")
            
            # 显示CDL数据
            cdl_types = ['construction_cdl', 'text_cdl', 'image_cdl', 'goal_cdl']
            for cdl_type in cdl_types:
                if cdl_type in problem and problem[cdl_type]:
                    print(f"\n{cdl_type}:")
                    for line in problem[cdl_type]:
                        print(f"  {line}")
            
            if 'annotation' in problem and problem['annotation']:
                print("\n注释:")
                print(problem['annotation'])
                
            if 'annotation_img' in problem and problem['annotation_img']:
                print("\n注释图片:")
                print(problem['annotation_img'])
            
            if problem['problem_answer']:
                print("\n答案与解析:")
                print(problem['problem_answer'])
                
            print("\n" + "="*60)
            
        elif cmd == 'e':
            # 导出题目
            if len(problem_ids) == 0:
                print("没有题目可导出")
                continue
                
            export_all = input("是否导出所有题目? (y/n): ").lower() == 'y'
            selected_ids = None
            
            if not export_all:
                print("当前题目列表:")
                for i, pid in enumerate(problem_ids[:10], 1):  # 只显示前10个
                    print(f"  {i}. {pid}")
                if len(problem_ids) > 10:
                    print("  ... 更多题目")
                
                id_input = input("请输入要导出的题目ID (用逗号分隔): ")
                selected_ids = [pid.strip() for pid in id_input.split(',') if pid.strip()]
            
            file_path = input("请输入导出文件路径 (回车自动生成): ").strip() or None
            result_path, msg = manager.export_to_json(selected_ids, file_path)
            print(msg)
            
        elif cmd.startswith('i '):
            # 导入题目
            file_path = cmd[2:]
            success, msg = manager.import_from_json(file_path)
            print(msg)
            if success:
                problem_ids = manager.get_all_problem_ids()
                current_index = 0 if problem_ids else -1
                current_problem_id = problem_ids[0] if problem_ids else None
                
        elif cmd == 'u':
            # 更新当前题目
            if not current_problem_id:
                print("请先选择一个题目")
                continue
                
            problem = manager.get_problem(current_problem_id)
            if not problem:
                print("题目不存在")
                continue
                
            print(f"\n===== 更新题目 {current_problem_id} =====")
            print("提示：直接回车保持当前值")
            
            # 显示当前值并获取新值
            updated_problem = {
                'source': input(f"来源 [{problem['source']}]: ") or problem['source'],
                'problem_text_cn': input(f"中文题干 [{problem['problem_text_cn'][:30]}...]: ") or problem['problem_text_cn'],
                'problem_text_en': input(f"英文题干 [{problem.get('problem_text_en', '')[:30]}...]: ") or problem.get('problem_text_en', ''),
                'problem_answer': input(f"答案与解析 [{problem.get('problem_answer', '')[:30]}...]: ") or problem.get('problem_answer', ''),
                'complexity_level': input(f"难度级别 [{problem['complexity_level'] or '未设置'}]: ") or problem['complexity_level'],
                'theorem_seqs': [seq.strip() for seq in input(f"定理序列 [{', '.join(problem['theorem_seqs'])}]: ").split(',') if seq.strip()] 
                               or problem['theorem_seqs']
            }
            
            # 更新题目类型
            print("\n当前题目类型: " + ", ".join(problem['problem_type']))
            print("可用题目类型:")
            types = manager.get_problem_types()
            for i, type_name in enumerate(types, 1):
                print(f"  {i}. {type_name}")
            
            type_input = input("请输入新的题目类型编号 (用逗号分隔，回车保持当前): ")
            if type_input.strip():
                type_indices = [int(idx.strip()) - 1 for idx in type_input.split(',') if idx.strip().isdigit()]
                updated_problem['problem_type'] = [types[i] for i in type_indices if 0 <= i < len(types)]
            else:
                updated_problem['problem_type'] = problem['problem_type']
            
            # 其他更新选项（图片、注释、CDL等）
            if input("是否更新题目图片? (y/n): ").lower() == 'y':
                img_count = input("请输入新的图片数量: ")
                if img_count.isdigit() and int(img_count) > 0:
                    updated_problem['problem_img'] = [input(f"图片 {i+1} URL: ") for i in range(int(img_count))]
            
            if input("是否更新注释? (y/n): ").lower() == 'y':
                updated_problem['annotation'] = input("请输入新的注释内容: ")
                if input("是否更新注释图片? (y/n): ").lower() == 'y':
                    updated_problem['annotation_img'] = input("新的注释图片URL: ")
            
            # 执行更新
            success, msg = manager.update_problem(current_problem_id, updated_problem)
            print(msg)
                
        elif cmd == 'd':
            # 删除当前题目
            if not current_problem_id:
                print("请先选择一个题目")
                continue
                
            confirm = input(f"确定要删除题目 {current_problem_id} 吗? (y/n): ")
            if confirm.lower() == 'y':
                success, msg = manager.delete_problem(current_problem_id)
                print(msg)
                if success:
                    problem_ids = manager.get_all_problem_ids()
                    current_index = 0 if problem_ids else -1
                    current_problem_id = problem_ids[0] if problem_ids else None
                    
        elif cmd == 't':
            # 显示所有题目类型
            print("\n可用的题目类型:")
            for i, type_name in enumerate(manager.get_problem_types(), 1):
                print(f"  {i}. {type_name}")
                
        else:
            print("未知命令，请重新输入")


if __name__ == "__main__":
    main()
