# 轻量全景浏览器
基于 PyQt5 + OpenGL 实现的本地全景图片查看器，支持标准等矩形投影全景图，体积极小、加载快速。

pyinstaller -w -F --clean --icon=pano.ico --add-data "pano.ico;." --name "全景浏览器" --hidden-import OpenGL --hidden-import OpenGL.GL --hidden-import OpenGL.GLU panoviewer_light.py


## 功能特性
- ✅ 支持 720° 等矩形全景图浏览（宽高比 2:1）
- ✅ 鼠标拖拽旋转视角，滚轮缩放视野
- ✅ 自动旋转功能，支持速度无级调节
- ✅ 全屏纯净模式，鼠标悬停顶部呼出工具栏
- ✅ 右键快捷菜单（打开/卸载/重置/旋转/全屏）
- ✅ 双击画面快速切换全屏，ESC 退出
- ✅ 自动适配显卡最大纹理尺寸，支持大分辨率全景图
- ✅ 单 EXE 打包，体积约 25MB，无需安装

## 操作说明
| 操作 | 功能 |
|------|------|
| 左键拖拽 | 旋转全景视角 |
| 滚轮滚动 | 缩放视野（30°~120°） |
| 左键双击画面 | 进入/退出全屏 |
| ESC 键 | 退出全屏 |
| 画面右键 | 弹出快捷菜单 |
| 全屏鼠标移到顶部 | 呼出工具栏 |

## 环境依赖
- Python 3.8+
- PyQt5
- PyOpenGL
- Pillow
- NumPy

一键安装依赖：
```bash
pip install PyQt5 PyOpenGL PyOpenGL_accelerate Pillow numpy
