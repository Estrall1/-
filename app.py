from flask import Flask, render_template, request, redirect, url_for, flash, session, jsonify
import os
import mysql.connector
from werkzeug.utils import secure_filename
from datetime import datetime

app = Flask(__name__)
app.config['SECRET_KEY'] = '19993605527'  # 密钥用来忘记密码时使用

# 文件上传配置
app.config['UPLOAD_FOLDER'] = 'static/uploads'
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB 最大文件大小

# 允许的文件扩展名
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'webp'}

# MySQL 数据库配置 - 根据你的实际配置修改
app.config['MYSQL_HOST'] = 'localhost'
app.config['MYSQL_USER'] = 'root'  # 默认用户名，根据你的设置修改
app.config['MYSQL_PASSWORD'] = '1234'  # 你的MySQL密码
app.config['MYSQL_DATABASE'] = 'sys'  # 使用你图片中显示的 test 数据库
app.config['MYSQL_PORT'] = 3306

# 默认登录凭据
DEFAULT_USERNAME = 'admin'
DEFAULT_PASSWORD = 'admin'

# 确保上传目录存在
if not os.path.exists(app.config['UPLOAD_FOLDER']):
    os.makedirs(app.config['UPLOAD_FOLDER'])

def allowed_file(filename):
    return '.' in filename and \
        filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def get_db_connection():
    """获取MySQL数据库连接"""
    try:
        conn = mysql.connector.connect(
            host=app.config['MYSQL_HOST'],
            user=app.config['MYSQL_USER'],
            password=app.config['MYSQL_PASSWORD'],
            database=app.config['MYSQL_DATABASE'],
            port=app.config['MYSQL_PORT']
        )
        return conn
    except mysql.connector.Error as e:
        print(f"数据库连接错误: {e}")
        return None

def init_database():
    """初始化数据库表"""
    conn = get_db_connection()
    if conn is None:
        print("无法连接数据库，请检查数据库配置")
        return

    cursor = conn.cursor()

    # 创建服装表
    cursor.execute('''
                   CREATE TABLE IF NOT EXISTS clothing_items (
                                                                 id INT AUTO_INCREMENT PRIMARY KEY,
                                                                 user_id VARCHAR(255) NOT NULL,
                       name VARCHAR(255) NOT NULL,
                       category VARCHAR(100) NOT NULL,
                       subcategory VARCHAR(100),
                       color VARCHAR(100),
                       brand VARCHAR(100),
                       season VARCHAR(50),
                       occasion VARCHAR(100),
                       image_path TEXT,
                       created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                       )
                   ''')

    # 创建搭配表
    cursor.execute('''
                   CREATE TABLE IF NOT EXISTS outfits (
                                                          id INT AUTO_INCREMENT PRIMARY KEY,
                                                          user_id VARCHAR(255) NOT NULL,
                       name VARCHAR(255) NOT NULL,
                       description TEXT,
                       items TEXT,  -- JSON格式存储服装ID列表
                       created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                       )
                   ''')

    conn.commit()
    cursor.close()
    conn.close()
    print("数据库初始化完成")

# 初始化数据库
init_database()

# 首页
@app.route('/')
def index():
    return render_template('main/index.html')

# 登录路由
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')

        if username == DEFAULT_USERNAME and password == DEFAULT_PASSWORD:
            session['user'] = username
            flash('登录成功！', 'success')
            return redirect(url_for('index'))
        else:
            flash('用户名或密码错误！', 'danger')

    return render_template('auth/login.html')

# 注册路由
@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form.get('username')
        email = request.form.get('email')
        password = request.form.get('password')
        confirm_password = request.form.get('confirm_password')

        if password != confirm_password:
            flash('两次输入的密码不一致！', 'danger')
        elif username == DEFAULT_USERNAME:
            flash('该用户名已存在！', 'danger')
        else:
            flash('注册成功！请使用默认账号 admin/admin 登录', 'success')
            return redirect(url_for('login'))

    return render_template('auth/register.html')

# 退出登录
@app.route('/logout')
def logout():
    session.pop('user', None)
    flash('您已成功退出登录！', 'success')
    return redirect(url_for('index'))

# 衣柜主页面
@app.route('/wardrobe')
def wardrobe():
    if 'user' not in session:
        flash('请先登录', 'warning')
        return redirect(url_for('login'))

    conn = get_db_connection()
    if conn is None:
        flash('数据库连接失败', 'danger')
        return render_template('wardrobe/wardrobe.html', clothing_items=[])

    cursor = conn.cursor(dictionary=True)
    cursor.execute(
        'SELECT * FROM clothing_items WHERE user_id = %s ORDER BY created_at DESC',
        (session['user'],)
    )
    clothing_items = cursor.fetchall()
    cursor.close()
    conn.close()

    return render_template('wardrobe/wardrobe.html', clothing_items=clothing_items)

# 添加服装
@app.route('/wardrobe/add', methods=['POST'])
def add_clothing():
    if 'user' not in session:
        return jsonify({'success': False, 'message': '请先登录'})

    conn = get_db_connection()
    if conn is None:
        return jsonify({'success': False, 'message': '数据库连接失败'})

    try:
        name = request.form.get('name')
        category = request.form.get('category')
        color = request.form.get('color')
        brand = request.form.get('brand')
        season = request.form.get('season')
        occasion = request.form.get('occasion')

        if not name or not category:
            return jsonify({'success': False, 'message': '名称和分类不能为空'})

        image_path = None
        if 'image' in request.files:
            file = request.files['image']
            if file and file.filename != '' and allowed_file(file.filename):
                # 生成安全的文件名
                filename = secure_filename(file.filename)
                # 添加时间戳避免重名
                timestamp = datetime.now().strftime('%Y%m%d_%H%M%S_')
                filename = timestamp + filename
                filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
                file.save(filepath)
                image_path = f"uploads/{filename}"  # 存储相对路径

        cursor = conn.cursor()
        cursor.execute(
            '''INSERT INTO clothing_items
                   (user_id, name, category, color, brand, season, occasion, image_path)
               VALUES (%s, %s, %s, %s, %s, %s, %s, %s)''',
            (session['user'], name, category, color, brand, season, occasion, image_path)
        )
        conn.commit()
        item_id = cursor.lastrowid
        cursor.close()
        conn.close()

        return jsonify({
            'success': True,
            'message': '添加成功',
            'item_id': item_id
        })

    except Exception as e:
        conn.close()
        return jsonify({'success': False, 'message': f'添加失败: {str(e)}'})

# 获取服装详情
@app.route('/wardrobe/item/<int:item_id>')
def get_clothing_item(item_id):
    if 'user' not in session:
        return jsonify({'success': False, 'message': '请先登录'})

    conn = get_db_connection()
    if conn is None:
        return jsonify({'success': False, 'message': '数据库连接失败'})

    cursor = conn.cursor(dictionary=True)
    cursor.execute(
        'SELECT * FROM clothing_items WHERE id = %s AND user_id = %s',
        (item_id, session['user'])
    )
    item = cursor.fetchone()
    cursor.close()
    conn.close()

    if item:
        return jsonify({
            'success': True,
            'item': item
        })
    else:
        return jsonify({'success': False, 'message': '服装不存在'})

# 更新服装信息
@app.route('/wardrobe/update/<int:item_id>', methods=['POST'])
def update_clothing(item_id):
    if 'user' not in session:
        return jsonify({'success': False, 'message': '请先登录'})

    conn = get_db_connection()
    if conn is None:
        return jsonify({'success': False, 'message': '数据库连接失败'})

    try:
        name = request.form.get('name')
        category = request.form.get('category')
        color = request.form.get('color')
        brand = request.form.get('brand')
        season = request.form.get('season')
        occasion = request.form.get('occasion')

        cursor = conn.cursor()

        # 检查图片是否更新
        image_path = None
        if 'image' in request.files:
            file = request.files['image']
            if file and file.filename != '' and allowed_file(file.filename):
                # 删除旧图片（如果有）
                cursor.execute(
                    'SELECT image_path FROM clothing_items WHERE id = %s AND user_id = %s',
                    (item_id, session['user'])
                )
                old_item = cursor.fetchone()

                if old_item and old_item[0]:
                    old_image_path = os.path.join('static', old_item[0])
                    if os.path.exists(old_image_path):
                        os.remove(old_image_path)

                # 保存新图片
                filename = secure_filename(file.filename)
                timestamp = datetime.now().strftime('%Y%m%d_%H%M%S_')
                filename = timestamp + filename
                filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
                file.save(filepath)
                image_path = f"uploads/{filename}"

        # 更新数据库
        if image_path:
            cursor.execute(
                '''UPDATE clothing_items
                   SET name = %s, category = %s, color = %s, brand = %s, season = %s, occasion = %s, image_path = %s
                   WHERE id = %s AND user_id = %s''',
                (name, category, color, brand, season, occasion, image_path, item_id, session['user'])
            )
        else:
            cursor.execute(
                '''UPDATE clothing_items
                   SET name = %s, category = %s, color = %s, brand = %s, season = %s, occasion = %s
                   WHERE id = %s AND user_id = %s''',
                (name, category, color, brand, season, occasion, item_id, session['user'])
            )

        conn.commit()
        cursor.close()
        conn.close()

        return jsonify({'success': True, 'message': '更新成功'})

    except Exception as e:
        conn.close()
        return jsonify({'success': False, 'message': f'更新失败: {str(e)}'})

# 删除服装
@app.route('/wardrobe/delete/<int:item_id>', methods=['POST'])
def delete_clothing(item_id):
    if 'user' not in session:
        return jsonify({'success': False, 'message': '请先登录'})

    conn = get_db_connection()
    if conn is None:
        return jsonify({'success': False, 'message': '数据库连接失败'})

    try:
        cursor = conn.cursor()

        # 获取图片路径以便删除文件
        cursor.execute(
            'SELECT image_path FROM clothing_items WHERE id = %s AND user_id = %s',
            (item_id, session['user'])
        )
        item = cursor.fetchone()

        if item and item[0]:
            image_path = os.path.join('static', item[0])
            if os.path.exists(image_path):
                os.remove(image_path)

        # 从数据库删除
        cursor.execute(
            'DELETE FROM clothing_items WHERE id = %s AND user_id = %s',
            (item_id, session['user'])
        )
        conn.commit()
        cursor.close()
        conn.close()

        return jsonify({'success': True, 'message': '删除成功'})

    except Exception as e:
        conn.close()
        return jsonify({'success': False, 'message': f'删除失败: {str(e)}'})

# 获取服装分类统计
@app.route('/wardrobe/statistics')
def get_wardrobe_statistics():
    if 'user' not in session:
        return jsonify({'success': False, 'message': '请先登录'})

    conn = get_db_connection()
    if conn is None:
        return jsonify({'success': False, 'message': '数据库连接失败'})

    cursor = conn.cursor(dictionary=True)

    # 按分类统计
    cursor.execute(
        '''SELECT category, COUNT(*) as count
           FROM clothing_items
           WHERE user_id = %s
           GROUP BY category''',
        (session['user'],)
    )
    category_stats = cursor.fetchall()

    # 按季节统计
    cursor.execute(
        '''SELECT season, COUNT(*) as count
           FROM clothing_items
           WHERE user_id = %s AND season IS NOT NULL AND season != ""
           GROUP BY season''',
        (session['user'],)
    )
    season_stats = cursor.fetchall()

    cursor.close()
    conn.close()

    return jsonify({
        'success': True,
        'category_stats': category_stats,
        'season_stats': season_stats
    })

# 其他功能页面的临时路由
@app.route('/search')
def search():
    return render_template('search/search.html')

@app.route('/virtual_tryon')
def virtual_tryon():
    return render_template('virtual_tryon/tryon.html')

@app.route('/recommendation')
def recommendation():
    return render_template('recommendation/recommendation.html')

@app.route('/style_analysis')
def style_analysis():
    return render_template('style_analysis/analysis.html')

# 错误处理
@app.errorhandler(404)
def not_found(error):
    return render_template('errors/404.html'), 404

@app.errorhandler(500)
def internal_error(error):
    return render_template('errors/500.html'), 500

if __name__ == '__main__':
    app.run(debug=True)