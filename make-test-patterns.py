from PIL import Image

# SIZE = (288, 192)
SIZE = (300, 216)

img = Image.new("RGB", SIZE, "white")
pix = img.load()
for i in range(img.size[0]):
    for j in range(img.size[1]):
        if i % 2 == j % 2:
            pix[i, j] = (0,0,0)
img.save('frames/checkerboard.png')


lines = Image.new("RGB", SIZE, "white")
pix = lines.load()
for i in range(lines.size[0]):
    for j in range(lines.size[1]):
        if i % 2:
            pix[i, j] = (0,0,0)
lines.save('frames/vlines.png')


lines = Image.new("RGB", SIZE, "white")
pix = lines.load()
for i in range(lines.size[0]):
    for j in range(lines.size[1]):
        if j % 2:
            pix[i, j] = (0,0,0)
lines.save('frames/hlines.png')


lines = Image.new("RGB", SIZE, "white")
lines.save('frames/0_white.png')

lines = Image.new("RGB", SIZE, "black")
lines.save('frames/z_black.png')
