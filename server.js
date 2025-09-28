const express = require('express');
const cors = require('cors');
const bodyParser = require('body-parser');
const fs = require('fs');
const path = require('path');

const app = express();
app.use(cors()); // 允许跨域请求
app.use(bodyParser.json()); // 解析JSON请求

// 配置本地文件路径（替换为你的实际路径）
const PROBLEMS_DIR = 'C:\\Users\\LENOVO\\Desktop\\data\\problems';
const IMAGES_DIR = 'C:\\Users\\LENOVO\\Desktop\\data\\images';

// 确保问题目录存在
if (!fs.existsSync(PROBLEMS_DIR)) {
    fs.mkdirSync(PROBLEMS_DIR, { recursive: true });
}

// 1. 提供图片访问（通过HTTP访问本地图片）
app.use('/images', express.static(IMAGES_DIR));

// 2. 获取指定ID的问题数据
app.get('/problems/:id', (req, res) => {
    const problemId = req.params.id;
    const filePath = path.join(PROBLEMS_DIR, `problem_${problemId}.json`);

    if (fs.existsSync(filePath)) {
        const data = fs.readFileSync(filePath, 'utf-8');
        res.json(JSON.parse(data));
    } else {
        // 如果文件不存在，返回空数据结构
        res.json({
            problem_id: parseInt(problemId),
            annotation: "",
            source: "",
            problem_text_cn: "",
            problem_text_en: "",
            problem_img: [],
            // 其他字段...
        });
    }
});

// 3. 保存问题数据到本地文件
app.post('/problems/:id', (req, res) => {
    const problemId = req.params.id;
    const problemData = req.body;
    const filePath = path.join(PROBLEMS_DIR, `problem_${problemId}.json`);

    try {
        fs.writeFileSync(filePath, JSON.stringify(problemData, null, 2), 'utf-8');
        res.json({ success: true, message: '保存成功' });
    } catch (error) {
        res.status(500).json({ success: false, message: '保存失败' });
    }
});

// 启动服务（端口3000）
const port = 3000;
app.listen(port, () => {
    console.log(`后端服务已启动：http://localhost:${port}`);
    console.log(`图片访问地址：http://localhost:${port}/images/`);
});