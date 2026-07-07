# 교권119 대표 이미지(600x600) 생성. 실행: python make_logo.py
from PIL import Image, ImageDraw, ImageFont

W = H = 600
navy = (27, 54, 88); amber = (244, 168, 76); white = (246, 248, 251); sky = (150, 175, 205)
img = Image.new("RGB", (W, H), navy)
d = ImageDraw.Draw(img)
bold = "C:/Windows/Fonts/malgunbd.ttf"
reg = "C:/Windows/Fonts/malgun.ttf"

# 얇은 배지 테두리
d.rounded_rectangle([28, 28, W - 28, H - 28], radius=36, outline=(58, 86, 124), width=3)

# 주황 도형 자체를 '연필'로 (아래 뾰족한 부분 = 깎인 연필심) + 위에 십자(119)
cx = 300
wood = (249, 210, 158)      # 깎인 나무
graphite = (38, 60, 96)     # 흑연 심
band = (238, 244, 249)      # 밴드
# 연필 몸통(주황)
d.polygon([(cx - 92, 96), (cx + 92, 96), (cx + 92, 206), (cx, 300), (cx - 92, 206)], fill=amber)
# 깎인 나무(원뿔부)
d.polygon([(cx - 92, 206), (cx + 92, 206), (cx, 300)], fill=wood)
# 흑연 심(끝)
d.polygon([(cx - 26, 262), (cx + 26, 262), (cx, 300)], fill=graphite)
# 몸통 밴드(금속 페룰 느낌)
d.rectangle([cx - 92, 120, cx + 92, 140], fill=band)
d.rectangle([cx - 92, 146, cx + 92, 152], fill=(228, 146, 58))
# 십자(연필 위 = 지우개 자리에 119)
d.rounded_rectangle([cx - 13, 44, cx + 13, 96], radius=5, fill=white)      # 세로
d.rounded_rectangle([cx - 35, 58, cx + 35, 78], radius=5, fill=white)      # 가로


def ctext(y, txt, font, fill):
    b = d.textbbox((0, 0), txt, font=font)
    d.text(((W - (b[2] - b[0])) // 2, y), txt, font=font, fill=fill)


# 워드마크: 교권(흰) + 119(앰버)
f = ImageFont.truetype(bold, 120)
t1, t2 = "교권", "119"
w1 = d.textbbox((0, 0), t1, font=f)[2]
w2 = d.textbbox((0, 0), t2, font=f)[2]
tot = w1 + w2 + 10
x0 = (W - tot) // 2
y = 330
d.text((x0, y), t1, font=f, fill=white)
d.text((x0 + w1 + 10, y), t2, font=f, fill=amber)

# 태그라인
ctext(500, "교육활동 보호 코파일럿", ImageFont.truetype(reg, 30), sky)

out = "C:/Users/chaey/gyogwon-mcp/gyogwon119_logo.png"
img.save(out)
print("saved 600x600 →", out)
