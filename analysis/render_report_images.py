"""Rasterize the report's Word-exported QA PDF; inspect resulting pages before delivery."""
from common import *
import fitz
from PIL import Image,ImageDraw

def main():
    folder=OUT/'qa/report_render';doc=fitz.open(folder/'report.pdf');pages=[]
    for i,page in enumerate(doc):
        path=folder/f'page-{i+1:02d}.png';page.get_pixmap(matrix=fitz.Matrix(1.5,1.5)).save(path)
        pages.append({'page':i+1,'text_chars':len(page.get_text()),'images':len(page.get_images()),'width':page.rect.width,'height':page.rect.height})
    for start in range(0,len(doc),6):
        canvas=Image.new('RGB',(1275,1800),'#e8e8e8');draw=ImageDraw.Draw(canvas)
        for j in range(start,min(start+6,len(doc))):
            im=Image.open(folder/f'page-{j+1:02d}.png');im.thumbnail((410,850));x=(j-start)%3*425+7;y=(j-start)//3*900+27;canvas.paste(im,(x,y));draw.text((x,y-20),str(j+1),fill='black')
        canvas.save(folder/f'contact-{start//6+1}.png')
    jsave({'pages':pages,'page_count':len(doc),'renderer':'Word COM export + PyMuPDF rasterization; bundled LibreOffice unavailable'},OUT/'qa/report_pagination.json')
    print('Rendered',len(doc),'page images',flush=True)
if __name__=='__main__':main()
