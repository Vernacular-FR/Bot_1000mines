from pathlib import Path
from PIL import Image

CELL_SIZE = 24
STRIDE = 25
IMG_PATH = Path(r"c:\Users\robin\Desktop\(ATELIER)\7-Code\Bot_demineur\Bot 1000mines-com\src\lib\s2_vision\s21_templates\s21_templates_analyzer\data_set\question_mark\chrome_R5AfBQWCSt.png")
OUTPUT_DIR = IMG_PATH.parent

def main() -> None:
    if not IMG_PATH.exists():
        raise FileNotFoundError(f"Image introuvable: {IMG_PATH}")
    img = Image.open(IMG_PATH).convert("RGB")
    width, height = img.size
    count = 0
    for top in range(0, height - CELL_SIZE + 1, STRIDE):
        for left in range(0, width - CELL_SIZE + 1, STRIDE):
            box = (left, top, left + CELL_SIZE, top + CELL_SIZE)
            tile = img.crop(box)
            tile_name = f"question_mark_{top // STRIDE:02d}_{left // STRIDE:02d}.png"
            tile.save(OUTPUT_DIR / tile_name)
            count += 1
    print(f"Saved {count} tiles of size {CELL_SIZE}x{CELL_SIZE}")

if __name__ == "__main__":
    main()
