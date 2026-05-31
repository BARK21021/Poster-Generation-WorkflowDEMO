import os
import torch
import numpy as np
from PIL import Image, ImageDraw, ImageFont
from matplotlib import font_manager

from ..sup import ROOT_FONTS
from comfy.utils import ProgressBar

def parse_fonts() -> dict:
    mgr = font_manager.FontManager()
    return {f"{font.name[0].upper()}/{font.name}": font.fname for font in mgr.ttflist}

class FL_TextOverlayNode:
    env_var_value = os.getenv("FL_USE_SYSTEM_FONTS", 'false').strip().lower()
    if env_var_value.strip() in ('true', '1', 't'):
        FONTS = parse_fonts()
    else:
        FONTS = {f"{str(font.stem)}": str(font) for font in ROOT_FONTS.glob("*.[to][tf][f]")}
    
    FONT_NAMES = sorted(FONTS.keys())
    if not FONT_NAMES: # Add a default if no fonts are found
        FONT_NAMES.append("Default")
        FONTS["Default"] = "default" # Placeholder, PIL will use its default

    DESCRIPTION = """
FL_TextOverlayNode applies a text overlay to an image.
You can specify the text, its position (as a percentage of image dimensions),
font size, font color, and choose from available system or local fonts.
Supports fractional stroke width for more precise control over text outlines.
"""

    # ComfyUI required class type
    class_type = "FL_TextOverlayNode"

    def __init__(self):
        pass

    @classmethod
    def INPUT_TYPES(s):
        return {
            "required": {
                "image": ("IMAGE",),
                "text": ("STRING", {"default": "Hello, ComfyUI!", "multiline": True}),
                "font": (s.FONT_NAMES, {"default": s.FONT_NAMES[0] if s.FONT_NAMES else "Default"}),
                "font_size": ("INT", {"default": 51, "min": 1, "step": 1}),
                "font_color_r": ("INT", {"default": 255, "min": 0, "max": 255, "step": 1, "description": "Red color value"}),
                "font_color_g": ("INT", {"default": 255, "min": 0, "max": 255, "step": 1, "description": "Green color value"}),
                "font_color_b": ("INT", {"default": 255, "min": 0, "max": 255, "step": 1, "description": "Blue color value"}),
                "x_pixel": ("INT", {"default": 512, "min": 0, "step": 1, "description": "X position in pixels from left (0 to image width)"}),
                "y_pixel": ("INT", {"default": 512, "min": 0, "step": 1, "description": "Y position in pixels from top (0 to image height)"}),
                "anchor": (["left-top", "center-top", "right-top",
                            "left-center", "center-center", "right-center",
                            "left-bottom", "center-bottom", "right-bottom"], 
                           {"default": "center-center", "description": "Text anchor point relative to X,Y coordinates"}),
            },
            "optional": {
                # 描边选项
                "stroke_enabled": ("BOOLEAN", {"default": False, "description": "Enable text stroke/outline"}),
                "stroke_width": ("FLOAT", {"default": 2.0, "min": 0.1, "max": 20.0, "step": 0.1, "description": "Stroke width in pixels"}),
                "stroke_color_r": ("INT", {"default": 0, "min": 0, "max": 255, "step": 1, "description": "Stroke red color value"}),
                "stroke_color_g": ("INT", {"default": 0, "min": 0, "max": 255, "step": 1, "description": "Stroke green color value"}),
                "stroke_color_b": ("INT", {"default": 0, "min": 0, "max": 255, "step": 1, "description": "Stroke blue color value"}),
                
                # 渐变色选项
                "gradient_enabled": ("BOOLEAN", {"default": False, "description": "Enable gradient text color"}),
                "gradient_type": (["horizontal", "vertical", "diagonal"], {"default": "horizontal", "description": "Gradient direction"}),
                "gradient_end_color_r": ("INT", {"default": 0, "min": 0, "max": 255, "step": 1, "description": "Gradient end red color value"}),
                "gradient_end_color_g": ("INT", {"default": 0, "min": 0, "max": 255, "step": 1, "description": "Gradient end green color value"}),
                "gradient_end_color_b": ("INT", {"default": 255, "min": 0, "max": 255, "step": 1, "description": "Gradient end blue color value"}),
            },
        }

    RETURN_TYPES = ("IMAGE",)
    FUNCTION = "apply_text_overlay"
    CATEGORY = "🏵️Fill Nodes/VFX"

    def _get_pil_anchor(self, anchor_str):
        # PIL anchor uses 'l' for left, 'm' for middle (horizontal), 'r' for right
        # 't' for top, 'm' for middle (vertical), 'b' for bottom
        # Example: "la" for left-ascent, "mm" for middle-middle
        # We simplify to 9 points. PIL's text_anchor is more nuanced with baselines.
        # We'll use the xy as the top-left of the text box and adjust based on text size for other anchors.
        # For direct PIL anchor mapping (approximations):
        mapping = {
            "left-top": "la", "center-top": "ma", "right-top": "ra",
            "left-center": "lm", "center-center": "mm", "right-center": "rm",
            "left-bottom": "lb", "center-bottom": "mb", "right-bottom": "rb"
        }
        return mapping.get(anchor_str, "mm") # default to middle-center

    def _interpolate_color(self, color1, color2, factor):
        """
        在两个颜色之间进行线性插值
        
        参数:
            color1 (tuple): 起始颜色 (R, G, B)
            color2 (tuple): 结束颜色 (R, G, B)
            factor (float): 插值因子 (0.0 到 1.0)
            
        返回:
            tuple: 插值后的颜色 (R, G, B)
        """
        r = int(color1[0] + (color2[0] - color1[0]) * factor)
        g = int(color1[1] + (color2[1] - color1[1]) * factor)
        b = int(color1[2] + (color2[2] - color1[2]) * factor)
        return (r, g, b)

    def _draw_text_with_stroke(self, draw, position, text, font, fill_color, stroke_color, stroke_width):
        """
        绘制带描边的文本，支持浮点型描边宽度
        
        参数:
            draw: PIL的ImageDraw对象
            position (tuple): 文本位置 (x, y)
            text (str): 要绘制的文本
            font: 字体对象
            fill_color (tuple): 填充颜色 (R, G, B)
            stroke_color (tuple): 描边颜色 (R, G, B)
            stroke_width (float): 描边宽度（支持浮点数）
        """
        # 对于浮点型描边宽度，我们需要更精细的处理
        # 计算整数边界，确保所有可能的像素都被覆盖
        int_width = int(max(1, stroke_width + 1))
        
        # 首先绘制描边，通过在周围多个位置绘制文本来实现
        for dx in range(-int_width, int_width + 1):
            for dy in range(-int_width, int_width + 1):
                # 跳过中心点，避免重复绘制
                if dx == 0 and dy == 0:
                    continue
                # 计算距离，只绘制在圆形范围内的点，使描边更自然
                # 这里支持浮点型描边宽度
                distance_squared = dx*dx + dy*dy
                if distance_squared <= stroke_width*stroke_width:
                    draw.text((position[0] + dx, position[1] + dy), text, font=font, fill=stroke_color)
        
        # 最后在中心绘制填充文本
        draw.text(position, text, font=font, fill=fill_color)
        
    def _draw_text_with_gradient(self, draw, position, text, font, start_color, end_color, gradient_type, stroke_enabled=False, stroke_color=None, stroke_width=2.0):
        """
        绘制带渐变色的文本，支持描边功能
        
        参数:
            draw: PIL的ImageDraw对象
            position (tuple): 文本位置 (x, y)
            text (str): 要绘制的文本
            font: 字体对象
            start_color (tuple): 起始颜色 (R, G, B)
            end_color (tuple): 结束颜色 (R, G, B)
            gradient_type (str): 渐变类型 ("horizontal", "vertical", "diagonal")
            stroke_enabled (bool): 是否启用描边
            stroke_color (tuple): 描边颜色 (R, G, B)
            stroke_width (float): 描边宽度（支持浮点数）
        """
        # 如果启用描边，先绘制描边
        if stroke_enabled and stroke_color is not None:
            self._draw_text_with_stroke(draw, position, text, font, start_color, stroke_color, stroke_width)
        
        # 获取文本的边界框
        bbox = draw.textbbox(position, text, font=font)
        text_width = bbox[2] - bbox[0]
        text_height = bbox[3] - bbox[1]
        
        # 创建一个临时图像来绘制渐变文本
        temp_img = Image.new('RGBA', (text_width + 10, text_height + 10), (0, 0, 0, 0))
        temp_draw = ImageDraw.Draw(temp_img)
        
        # 如果文本包含换行符，需要逐行处理
        if '\n' in text:
            lines = text.split('\n')
            line_height = text_height // len(lines)
            
            for i, line in enumerate(lines):
                # 获取当前行的边界框
                line_bbox = temp_draw.textbbox((0, 0), line, font=font)
                line_width = line_bbox[2] - line_bbox[0]
                
                # 根据渐变类型绘制每一行
                if gradient_type == "horizontal":
                    # 水平渐变
                    for x in range(0, line_width, 2):  # 每2像素采样一次，提高性能
                        factor = x / line_width if line_width > 0 else 0
                        color = self._interpolate_color(start_color, end_color, factor)
                        # 绘制单个字符或字符的一部分
                        char_width = 2  # 每次绘制2像素宽度的文本片段
                        for char_idx, char in enumerate(line):
                            char_bbox = temp_draw.textbbox((0, 0), char, font=font)
                            char_start = char_bbox[0]
                            char_end = char_bbox[2] - char_start
                            if x >= char_start and x < char_start + char_end:
                                temp_draw.text((x, i * line_height), char, font=font, fill=color)
                
                elif gradient_type == "vertical":
                    # 垂直渐变 - 每行使用不同的颜色
                    factor = i / (len(lines) - 1) if len(lines) > 1 else 0
                    color = self._interpolate_color(start_color, end_color, factor)
                    temp_draw.text((0, i * line_height), line, font=font, fill=color)
                
                elif gradient_type == "diagonal":
                    # 对角渐变
                    for x in range(0, line_width, 2):
                        # 计算对角线上的位置
                        diag_pos = (x + i * line_width) / (text_width + text_height)
                        factor = min(1.0, max(0.0, diag_pos))
                        color = self._interpolate_color(start_color, end_color, factor)
                        # 绘制单个字符或字符的一部分
                        for char_idx, char in enumerate(line):
                            char_bbox = temp_draw.textbbox((0, 0), char, font=font)
                            char_start = char_bbox[0]
                            char_end = char_bbox[2] - char_start
                            if x >= char_start and x < char_start + char_end:
                                temp_draw.text((x, i * line_height), char, font=font, fill=color)
        else:
            # 单行文本处理
            if gradient_type == "horizontal":
                # 水平渐变
                for x in range(0, text_width, 2):  # 每2像素采样一次，提高性能
                    factor = x / text_width if text_width > 0 else 0
                    color = self._interpolate_color(start_color, end_color, factor)
                    # 绘制单个字符或字符的一部分
                    for char_idx, char in enumerate(text):
                        char_bbox = temp_draw.textbbox((0, 0), char, font=font)
                        char_start = char_bbox[0]
                        char_end = char_bbox[2] - char_start
                        if x >= char_start and x < char_start + char_end:
                            temp_draw.text((x, 0), char, font=font, fill=color)
            
            elif gradient_type == "vertical":
                # 垂直渐变
                for y in range(0, text_height, 2):
                    factor = y / text_height if text_height > 0 else 0
                    color = self._interpolate_color(start_color, end_color, factor)
                    # 创建一个只包含当前行像素的临时文本
                    temp_draw.text((0, y), text, font=font, fill=color)
            
            elif gradient_type == "diagonal":
                # 对角渐变
                for x in range(0, text_width, 2):
                    for y in range(0, text_height, 2):
                        # 计算对角线上的位置
                        diag_pos = (x + y) / (text_width + text_height)
                        factor = min(1.0, max(0.0, diag_pos))
                        color = self._interpolate_color(start_color, end_color, factor)
                        # 绘制单个像素点
                        temp_draw.point((x, y), fill=color)
        
        # 将临时图像粘贴到主图像上
        draw.bitmap(position, temp_img.convert('1'))

    def _fit_text_to_canvas(self, text, font_name, initial_font_size, max_width, max_height, stroke_enabled=False, stroke_width=2.0):
        """
        根据画布大小调整文字大小，确保文字不超出指定的最大宽度和高度
        
        参数:
            text: 要绘制的文本
            font_name: 字体名称
            initial_font_size: 初始字体大小
            max_width: 最大宽度
            max_height: 最大高度
            stroke_enabled: 是否启用描边
            stroke_width: 描边宽度
            
        返回:
            (调整后的字体对象, 调整后的字体大小)
        """
        # 计算描边边距
        stroke_margin = stroke_width * 2 if stroke_enabled else 0
        
        # 加载字体
        try:
            if font_name == "Default" or self.FONTS[font_name] == "default":
                current_font = ImageFont.load_default()
                # 如果是默认字体，尝试估计合适的大小
                current_size = initial_font_size
                while current_size > 1:
                    try:
                        # 对于默认字体，尝试缩放
                        temp_img = Image.new('RGB', (1, 1))
                        temp_draw = ImageDraw.Draw(temp_img)
                        # 创建临时字体对象并测量文本边界
                        temp_font = ImageFont.load_default()
                        # 估算字体大小，这里使用简化方法
                        test_width, test_height = temp_draw.textlength(text, font=temp_font) * (current_size / 12), current_size
                        
                        if test_width + stroke_margin <= max_width and test_height + stroke_margin <= max_height:
                            break
                        current_size = int(current_size * 0.95)
                    except:
                        break
                return current_font, current_size
            else:
                current_size = initial_font_size
                while current_size > 1:
                    try:
                        current_font = ImageFont.truetype(self.FONTS[font_name], current_size)
                        
                        # 创建临时图像和绘图上下文来测量文本
                        temp_img = Image.new('RGB', (1, 1))
                        temp_draw = ImageDraw.Draw(temp_img)
                        
                        # 获取文本边界框
                        try:
                            bbox = temp_draw.textbbox((0, 0), text, font=current_font)
                            text_width = bbox[2] - bbox[0]
                            text_height = bbox[3] - bbox[1]
                        except:
                            # 如果无法获取边界框，使用文本长度估算
                            text_width = temp_draw.textlength(text, font=current_font)
                            # 估算高度（通常为字体大小的1.2倍）
                            text_height = current_size * 1.2
                        
                        # 检查是否在边界内，考虑描边边距
                        if text_width + stroke_margin <= max_width and text_height + stroke_margin <= max_height:
                            break
                        
                        # 缩小字体大小
                        current_size = int(current_size * 0.95)
                    except Exception as e:
                        # 如果加载字体失败，尝试减小字体大小
                        print(f"Warning: Failed to load font at size {current_size}: {e}")
                        current_size = int(current_size * 0.95)
                
                # 确保能加载最终字体
                try:
                    final_font = ImageFont.truetype(self.FONTS[font_name], current_size)
                    return final_font, current_size
                except:
                    # 如果失败，回退到默认字体
                    print("Warning: Falling back to default font")
                    return ImageFont.load_default(), current_size
        except Exception as e:
            print(f"Error in _fit_text_to_canvas: {e}")
            # 回退到默认字体
            return ImageFont.load_default(), max(1, int(initial_font_size * 0.5))
    
    def _wrap_text(self, text, font, max_width):
        """
        自动换行文本以适应最大宽度
        
        参数:
            text: 要换行的文本
            font: 字体对象
            max_width: 最大宽度
            
        返回:
            换行后的文本
        """
        lines = []
        # 先按现有换行符分割
        paragraphs = text.split('\n')
        
        for paragraph in paragraphs:
            if not paragraph.strip():
                lines.append('')
                continue
                
            words = paragraph.split(' ')
            if not words:
                continue
                
            current_line = words[0]
            
            # 创建临时绘图上下文来测量文本
            temp_img = Image.new('RGB', (1, 1))
            temp_draw = ImageDraw.Draw(temp_img)
            
            for word in words[1:]:
                test_line = current_line + ' ' + word
                try:
                    # 尝试使用textlength或textbbox
                    try:
                        width = temp_draw.textlength(test_line, font=font)
                    except:
                        # 回退方法
                        bbox = temp_draw.textbbox((0, 0), test_line, font=font)
                        width = bbox[2] - bbox[0]
                    
                    if width <= max_width:
                        current_line = test_line
                    else:
                        lines.append(current_line)
                        current_line = word
                except:
                    # 如果测量失败，保守换行
                    lines.append(current_line)
                    current_line = word
                    
            lines.append(current_line)
            
        return '\n'.join(lines)
    
    def apply_text_overlay(self, image: torch.Tensor, text: str, font: str, font_size: int, font_color_r: int, font_color_g: int, font_color_b: int, x_pixel: int, y_pixel: int, anchor: str, stroke_enabled=False, stroke_width=2.0, stroke_color_r=0, stroke_color_g=0, stroke_color_b=0, gradient_enabled=False, gradient_type="horizontal", gradient_end_color_r=0, gradient_end_color_g=0, gradient_end_color_b=255):
        batch_size = image.shape[0]
        result_images = []
        
        font_color_rgb = (font_color_r, font_color_g, font_color_b)
        stroke_color = (stroke_color_r, stroke_color_g, stroke_color_b)
        gradient_end_color = (gradient_end_color_r, gradient_end_color_g, gradient_end_color_b)

        pbar = ProgressBar(batch_size)
        for i in range(batch_size):
            img_tensor = image[i]
            pil_image = Image.fromarray((img_tensor.cpu().numpy() * 255).astype(np.uint8))
            pil_image = pil_image.convert("RGB") # Ensure it's RGB
            
            draw = ImageDraw.Draw(pil_image)
            
            img_width, img_height = pil_image.size
            # 计算描边边距
            stroke_margin = stroke_width * 2 if stroke_enabled else 0
            
            # 设置安全边界（避免紧贴边缘）
            margin = 2 + stroke_margin
            max_text_width = img_width - 2 * margin
            max_text_height = img_height - 2 * margin
            
            # 确保坐标在图像范围内
            x_abs = max(margin, min(img_width - margin, x_pixel))
            y_abs = max(margin, min(img_height - margin, y_pixel))

            # 初始字体加载和文本处理
            try:
                # 首先尝试自动换行以适应宽度
                # 先加载一个临时字体来测量文本
                temp_font = None
                try:
                    if font == "Default" or self.FONTS[font] == "default":
                        temp_font = ImageFont.load_default()
                    else:
                        temp_font = ImageFont.truetype(self.FONTS[font], font_size)
                except:
                    temp_font = ImageFont.load_default()
                
                # 尝试自动换行
                wrapped_text = self._wrap_text(text, temp_font, max_text_width)
                
                # 调整字体大小以适应画布
                adjusted_font, adjusted_size = self._fit_text_to_canvas(
                    wrapped_text, font, font_size, max_text_width, max_text_height, 
                    stroke_enabled, stroke_width
                )
                
                # 对于换行后的文本，再次检查大小
                # 计算文本边界框
                temp_img = Image.new('RGB', (1, 1))
                temp_draw = ImageDraw.Draw(temp_img)
                try:
                    text_bbox = temp_draw.textbbox((0, 0), wrapped_text, font=adjusted_font)
                    text_width = text_bbox[2] - text_bbox[0]
                    text_height = text_bbox[3] - text_bbox[1]
                except:
                    # 回退估算方法
                    text_width = temp_draw.textlength(wrapped_text.split('\n')[0], font=adjusted_font)
                    line_count = wrapped_text.count('\n') + 1
                    text_height = adjusted_size * line_count * 1.2
                
                # 根据锚点调整实际绘制位置
                anchor_horizontal, anchor_vertical = anchor.split('-')
                
                # 计算原始锚点位置
                if anchor_horizontal == 'left':
                    draw_x = x_abs
                elif anchor_horizontal == 'right':
                    draw_x = x_abs - text_width
                else:  # center
                    draw_x = x_abs - text_width / 2
                    
                if anchor_vertical == 'top':
                    draw_y = y_abs
                elif anchor_vertical == 'bottom':
                    draw_y = y_abs - text_height
                else:  # center
                    draw_y = y_abs - text_height / 2
                
                # 位置边界检查和调整
                # 水平边界调整
                if draw_x < margin:
                    # 向左超出边界，拉回到左边界
                    draw_x = margin
                elif draw_x + text_width > img_width - margin:
                    # 向右超出边界，拉回到右边界
                    draw_x = img_width - margin - text_width
                
                # 垂直边界调整
                if draw_y < margin:
                    # 向上超出边界，拉回到上边界
                    draw_y = margin
                elif draw_y + text_height > img_height - margin:
                    # 向下超出边界，拉回到下边界
                    draw_y = img_height - margin - text_height
                
                # 再次检查，如果调整位置后仍然超出，可能需要进一步缩小字体
                # 这种情况很少发生，因为_fit_text_to_canvas已经考虑了最大尺寸
                if (draw_x < margin or draw_x + text_width > img_width - margin or 
                    draw_y < margin or draw_y + text_height > img_height - margin):
                    # 进一步缩小字体
                    print("Warning: Text still exceeds canvas after position adjustment. Further reducing font size.")
                    
                    # 计算更严格的最大尺寸
                    stricter_max_width = img_width - 2 * margin
                    stricter_max_height = img_height - 2 * margin
                    
                    # 进一步缩小字体
                    adjusted_font, adjusted_size = self._fit_text_to_canvas(
                        wrapped_text, font, int(adjusted_size * 0.8), stricter_max_width, stricter_max_height,
                        stroke_enabled, stroke_width
                    )
                    
                    # 重新计算文本边界
                    try:
                        text_bbox = temp_draw.textbbox((0, 0), wrapped_text, font=adjusted_font)
                        text_width = text_bbox[2] - text_bbox[0]
                        text_height = text_bbox[3] - text_bbox[1]
                    except:
                        text_width = temp_draw.textlength(wrapped_text.split('\n')[0], font=adjusted_font)
                        line_count = wrapped_text.count('\n') + 1
                        text_height = adjusted_size * line_count * 1.2
                    
                    # 重新调整到安全位置（居中）
                    draw_x = (img_width - text_width) / 2
                    draw_y = (img_height - text_height) / 2
                
                # 绘制文本，支持描边和渐变色
                if gradient_enabled:
                    # 使用渐变色绘制文本（可能同时带有描边）
                    self._draw_text_with_gradient(
                        draw, (draw_x, draw_y), wrapped_text, adjusted_font, 
                        font_color_rgb, gradient_end_color, gradient_type,
                        stroke_enabled, stroke_color, stroke_width
                    )
                elif stroke_enabled:
                    # 仅使用描边绘制文本
                    self._draw_text_with_stroke(
                        draw, (draw_x, draw_y), wrapped_text, adjusted_font,
                        font_color_rgb, stroke_color, stroke_width
                    )
                else:
                    # 常规文本绘制
                    draw.text((draw_x, draw_y), wrapped_text, font=adjusted_font, fill=font_color_rgb)
                    
            except Exception as e:
                print(f"Error processing text overlay: {e}")
                # 失败时使用最小字体和默认位置作为最后的回退
                try:
                    fallback_font = ImageFont.load_default()
                    draw.text((margin, margin), "Text rendering failed", font=fallback_font, fill=(255, 0, 0))
                except:
                    pass


            img_array = np.array(pil_image).astype(np.float32) / 255.0
            result_images.append(torch.from_numpy(img_array).unsqueeze(0))
            pbar.update_absolute(i + 1, batch_size)
            
        final_tensor = torch.cat(result_images, dim=0)
        return (final_tensor,)