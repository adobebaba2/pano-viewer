import sys
import os
import math
import numpy as np
from PIL import Image
from PyQt5.QtWidgets import *
from PyQt5.QtCore import *
from PyQt5.QtGui import *
from PyQt5.QtOpenGL import QGLWidget
from OpenGL.GL import *
from OpenGL.GLU import *


def resource_path(relative_path):
    """资源路径适配：兼容开发环境与打包后单EXE环境"""
    if hasattr(sys, '_MEIPASS'):
        return os.path.join(sys._MEIPASS, relative_path)
    return os.path.join(os.path.abspath("."), relative_path)


class PanoGLWidget(QGLWidget):
    """全景OpenGL渲染控件"""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumSize(800, 600)
        
        # 视角参数
        self.yaw = 0.0
        self.pitch = 0.0
        self.fov = 90.0
        self.texture_id = None
        self.sphere_vertices = None
        self.sphere_texcoords = None
        self.sphere_indices = None
        self.max_texture_size = 8192
        
        # 鼠标状态
        self.last_pos = None
        self.has_image = False

        # 自动旋转
        self.auto_rotate_speed = 0.05
        self.rotate_timer = QTimer(self)
        self.rotate_timer.timeout.connect(self._auto_rotate_step)

    def start_auto_rotate(self):
        if not self.rotate_timer.isActive():
            self.rotate_timer.start(30)

    def stop_auto_rotate(self):
        if self.rotate_timer.isActive():
            self.rotate_timer.stop()

    def toggle_auto_rotate(self):
        if self.rotate_timer.isActive():
            self.stop_auto_rotate()
            return False
        else:
            self.start_auto_rotate()
            return True

    def set_rotate_speed(self, speed):
        self.auto_rotate_speed = speed

    def _auto_rotate_step(self):
        if self.has_image:
            self.yaw += self.auto_rotate_speed
            if self.yaw > 360.0:
                self.yaw -= 360.0
            self.update()

    def initializeGL(self):
        # 白色背景
        glClearColor(1.0, 1.0, 1.0, 1.0)
        glEnable(GL_TEXTURE_2D)
        glEnable(GL_DEPTH_TEST)
        glDepthFunc(GL_LEQUAL)
        glPixelStorei(GL_UNPACK_ALIGNMENT, 1)
        
        # 获取显卡支持的最大纹理尺寸
        self.max_texture_size = glGetIntegerv(GL_MAX_TEXTURE_SIZE)
        # 构建球体
        self._build_sphere(radius=1.0, stacks=64, slices=128)

    def resizeGL(self, w, h):
        glViewport(0, 0, w, h)
        glMatrixMode(GL_PROJECTION)
        glLoadIdentity()
        gluPerspective(self.fov, w / h if h != 0 else 1.0, 0.001, 100.0)
        glMatrixMode(GL_MODELVIEW)

    def paintGL(self):
        glClear(GL_COLOR_BUFFER_BIT | GL_DEPTH_BUFFER_BIT)
        glLoadIdentity()
        
        if not self.has_image or self.texture_id is None:
            return
        
        glRotatef(self.pitch, 1.0, 0.0, 0.0)
        glRotatef(self.yaw, 0.0, 1.0, 0.0)
        
        glBindTexture(GL_TEXTURE_2D, self.texture_id)
        self._draw_sphere()

    def _build_sphere(self, radius=1.0, stacks=64, slices=128):
        vertices = []
        texcoords = []
        indices = []
        
        for i in range(stacks + 1):
            lat = math.pi * i / stacks
            sin_lat = math.sin(lat)
            cos_lat = math.cos(lat)
            
            for j in range(slices + 1):
                lon = 2 * math.pi * j / slices
                sin_lon = math.sin(lon)
                cos_lon = math.cos(lon)
                
                x = radius * cos_lon * sin_lat
                y = radius * cos_lat
                z = radius * sin_lon * sin_lat
                
                vertices.append([x, y, z])
                texcoords.append([j / slices, 1.0 - i / stacks])
        
        for i in range(stacks):
            for j in range(slices):
                first = i * (slices + 1) + j
                second = first + slices + 1
                indices.append(first)
                indices.append(second)
                indices.append(first + 1)
                indices.append(second)
                indices.append(second + 1)
                indices.append(first + 1)
        
        self.sphere_vertices = np.array(vertices, dtype=np.float32)
        self.sphere_texcoords = np.array(texcoords, dtype=np.float32)
        self.sphere_indices = np.array(indices, dtype=np.uint32)

    def _draw_sphere(self):
        glEnableClientState(GL_VERTEX_ARRAY)
        glEnableClientState(GL_TEXTURE_COORD_ARRAY)
        
        glVertexPointer(3, GL_FLOAT, 0, self.sphere_vertices)
        glTexCoordPointer(2, GL_FLOAT, 0, self.sphere_texcoords)
        
        glDrawElements(GL_TRIANGLES, len(self.sphere_indices), GL_UNSIGNED_INT, self.sphere_indices)
        
        glDisableClientState(GL_VERTEX_ARRAY)
        glDisableClientState(GL_TEXTURE_COORD_ARRAY)

    def load_image(self, file_path):
        """加载全景图片（优化速度+大图片兼容）"""
        try:
            self.makeCurrent()
            
            # 读取图片
            img = Image.open(file_path).convert("RGB")
            width, height = img.size
            
            # 自动缩放到显卡支持的最大尺寸内，保证兼容性
            max_dim = max(width, height)
            if max_dim > self.max_texture_size:
                scale = self.max_texture_size / max_dim
                new_w = int(width * scale)
                new_h = int(height * scale)
                img = img.resize((new_w, new_h), Image.LANCZOS)
            
            # 翻转并转换为连续内存数组
            img = img.transpose(Image.FLIP_TOP_BOTTOM)
            img_data = np.ascontiguousarray(img, dtype=np.uint8)
            w, h = img.size
            
            # 释放旧纹理
            if self.texture_id is not None:
                glDeleteTextures(1, [self.texture_id])
            
            # 创建基础纹理，加载速度快，兼容性好
            self.texture_id = glGenTextures(1)
            glBindTexture(GL_TEXTURE_2D, self.texture_id)
            glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_WRAP_S, GL_REPEAT)
            glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_WRAP_T, GL_CLAMP_TO_EDGE)
            glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MIN_FILTER, GL_LINEAR)
            glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MAG_FILTER, GL_LINEAR)
            glTexImage2D(GL_TEXTURE_2D, 0, GL_RGB, w, h, 0, GL_RGB, GL_UNSIGNED_BYTE, img_data)
            
            self.has_image = True
            self.update()
            return True
            
        except Exception as e:
            print(f"加载失败详情: {str(e)}")
            return False
        finally:
            # 确保上下文总是被释放，避免泄漏
            try:
                self.doneCurrent()
            except:
                pass

    def unload_image(self):
        """卸载当前全景图"""
        try:
            self.makeCurrent()
            if self.texture_id is not None:
                glDeleteTextures(1, [self.texture_id])
                self.texture_id = None
            self.has_image = False
            self.stop_auto_rotate()
            self.update()
        finally:
            try:
                self.doneCurrent()
            except:
                pass

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.last_pos = event.pos()

    def mouseMoveEvent(self, event):
        if self.last_pos is not None and event.buttons() & Qt.LeftButton:
            dx = event.x() - self.last_pos.x()
            dy = event.y() - self.last_pos.y()
            
            self.yaw -= dx * 0.3
            self.pitch -= dy * 0.3
            self.pitch = max(-89.0, min(89.0, self.pitch))
            
            self.last_pos = event.pos()
            self.update()
        super().mouseMoveEvent(event)

    def wheelEvent(self, event):
        delta = event.angleDelta().y() / 120
        self.fov -= delta * 5.0
        self.fov = max(30.0, min(120.0, self.fov))
        
        w, h = self.width(), self.height()
        glMatrixMode(GL_PROJECTION)
        glLoadIdentity()
        gluPerspective(self.fov, w / h if h != 0 else 1.0, 0.001, 100.0)
        glMatrixMode(GL_MODELVIEW)
        self.update()

    def reset_view(self):
        self.yaw = 0.0
        self.pitch = 0.0
        self.fov = 90.0
        
        w, h = self.width(), self.height()
        glMatrixMode(GL_PROJECTION)
        glLoadIdentity()
        gluPerspective(self.fov, w / h if h != 0 else 1.0, 0.001, 100.0)
        glMatrixMode(GL_MODELVIEW)
        self.update()


class PanoViewerWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("全景浏览器 轻量版")
        self.resize(1200, 800)
        # 设置窗口标题栏+任务栏图标
        self.setWindowIcon(QIcon(resource_path("pano.ico")))
        
        # 中心渲染控件
        self.gl_widget = PanoGLWidget()
        self.setCentralWidget(self.gl_widget)
        self.gl_widget.installEventFilter(self)
        
        # 启用右键自定义菜单
        self.gl_widget.setContextMenuPolicy(Qt.CustomContextMenu)
        self.gl_widget.customContextMenuRequested.connect(self.show_context_menu)
        
        # 创建自定义悬浮工具栏
        self.create_toolbar()
        
        # 底部状态栏
        self.statusBar().showMessage("操作说明：拖拽旋转 | 滚轮缩放 | 双击/ESC切换全屏 | 右键更多功能")
        
        self.is_fullscreen = False

    def create_toolbar(self):
        """创建自定义悬浮工具栏"""
        self.toolbar_widget = QWidget(self.gl_widget)
        self.toolbar_widget.setStyleSheet("background-color: rgba(240, 240, 240, 230); border-bottom: 1px solid #ccc;")
        toolbar_layout = QHBoxLayout(self.toolbar_widget)
        toolbar_layout.setContentsMargins(8, 6, 8, 6)
        toolbar_layout.setSpacing(8)
        
        # 按钮控件
        self.open_btn = QPushButton("打开全景图片")
        self.unload_btn = QPushButton("卸载图片")
        self.reset_btn = QPushButton("重置视角")
        self.rotate_btn = QPushButton("自动旋转")
        self.fullscreen_btn = QPushButton("全屏")
        
        # 速度调节
        speed_label = QLabel("速度:")
        self.speed_slider = QSlider(Qt.Horizontal)
        self.speed_slider.setRange(1, 200)
        self.speed_slider.setValue(5)
        self.speed_slider.setFixedWidth(120)
        self.speed_label = QLabel("0.05")
        
        # 添加到布局
        toolbar_layout.addWidget(self.open_btn)
        toolbar_layout.addWidget(self.unload_btn)
        toolbar_layout.addWidget(self.reset_btn)
        toolbar_layout.addWidget(self.rotate_btn)
        toolbar_layout.addWidget(speed_label)
        toolbar_layout.addWidget(self.speed_slider)
        toolbar_layout.addWidget(self.speed_label)
        toolbar_layout.addStretch()
        toolbar_layout.addWidget(self.fullscreen_btn)
        
        # 绑定事件
        self.open_btn.clicked.connect(self.open_image)
        self.unload_btn.clicked.connect(self.unload_image)
        self.reset_btn.clicked.connect(self.gl_widget.reset_view)
        self.rotate_btn.clicked.connect(self.toggle_auto_rotate)
        self.fullscreen_btn.clicked.connect(self.toggle_fullscreen)
        self.speed_slider.valueChanged.connect(self.update_rotate_speed)
        
        # 初始位置
        self.toolbar_widget.move(0, 0)

    def show_context_menu(self, pos):
        """右键弹出菜单"""
        menu = QMenu(self)
        
        # 基础操作
        open_action = menu.addAction("打开全景图片")
        open_action.triggered.connect(self.open_image)
        
        unload_action = menu.addAction("卸载图片")
        unload_action.triggered.connect(self.unload_image)
        
        reset_action = menu.addAction("重置视角")
        reset_action.triggered.connect(self.gl_widget.reset_view)
        
        menu.addSeparator()
        
        # 自动旋转（状态自动切换文字）
        if self.gl_widget.rotate_timer.isActive():
            rotate_action = menu.addAction("停止旋转")
        else:
            rotate_action = menu.addAction("自动旋转")
        rotate_action.triggered.connect(self.toggle_auto_rotate)
        
        menu.addSeparator()
        
        # 全屏（状态自动切换文字）
        if self.is_fullscreen:
            fullscreen_action = menu.addAction("退出全屏")
        else:
            fullscreen_action = menu.addAction("全屏")
        fullscreen_action.triggered.connect(self.toggle_fullscreen)
        
        # 在鼠标位置显示菜单
        menu.exec_(self.gl_widget.mapToGlobal(pos))

    def resizeEvent(self, event):
        """窗口尺寸变化时同步工具栏宽度"""
        super().resizeEvent(event)
        self.toolbar_widget.resize(self.gl_widget.width(), self.toolbar_widget.sizeHint().height())

    def eventFilter(self, obj, event):
        """双击切换全屏 + 全屏下悬停顶部呼出工具栏"""
        if obj == self.gl_widget:
            # 左键双击切换全屏
            if event.type() == QEvent.MouseButtonDblClick and event.button() == Qt.LeftButton:
                self.toggle_fullscreen()
                return True
            
            # 全屏下鼠标悬停顶部呼出工具栏
            if event.type() == QEvent.MouseMove and self.is_fullscreen:
                mouse_y = event.y()
                bar_h = self.toolbar_widget.height()
                if mouse_y < 30 or (self.toolbar_widget.isVisible() and mouse_y < bar_h):
                    if not self.toolbar_widget.isVisible():
                        self.toolbar_widget.show()
                else:
                    if self.toolbar_widget.isVisible():
                        self.toolbar_widget.hide()
        
        return super().eventFilter(obj, event)

    def update_rotate_speed(self, value):
        speed = value / 100.0
        self.gl_widget.set_rotate_speed(speed)
        self.speed_label.setText(f"{speed:.2f}")

    def open_image(self):
        file_path, _ = QFileDialog.getOpenFileName(
            self, "选择全景图片", "",
            "全景图片 (*.jpg *.jpeg *.png *.bmp *.webp);;所有文件 (*.*)"
        )
        if not file_path:
            return
        
        success = self.gl_widget.load_image(file_path)
        if success:
            self.statusBar().showMessage(f"加载成功：{file_path}")
        else:
            self.statusBar().showMessage("加载失败，请检查图片文件是否损坏")

    def unload_image(self):
        self.gl_widget.unload_image()
        self.rotate_btn.setText("自动旋转")
        self.statusBar().showMessage("已卸载当前全景图")

    def toggle_auto_rotate(self):
        if not self.gl_widget.has_image:
            self.statusBar().showMessage("请先打开全景图片后再使用自动旋转")
            return
        
        is_running = self.gl_widget.toggle_auto_rotate()
        if is_running:
            self.rotate_btn.setText("停止旋转")
            self.statusBar().showMessage("自动旋转已开启")
        else:
            self.rotate_btn.setText("自动旋转")
            self.statusBar().showMessage("自动旋转已停止")

    def toggle_fullscreen(self):
        if not self.is_fullscreen:
            # 进入全屏：隐藏状态栏，工具栏默认隐藏
            self.showFullScreen()
            self.is_fullscreen = True
            self.statusBar().hide()
            self.toolbar_widget.hide()
            self.fullscreen_btn.setText("退出全屏")
        else:
            # 退出全屏：恢复状态栏，工具栏常显
            self.showNormal()
            self.is_fullscreen = False
            self.statusBar().show()
            self.toolbar_widget.show()
            self.fullscreen_btn.setText("全屏")

    def keyPressEvent(self, event):
        if event.key() == Qt.Key_Escape and self.is_fullscreen:
            self.toggle_fullscreen()
        else:
            super().keyPressEvent(event)


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = PanoViewerWindow()
    window.show()
    sys.exit(app.exec_())