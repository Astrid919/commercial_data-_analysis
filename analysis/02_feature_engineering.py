"""Conservative parsing: separate per-unit mass from concentration/container mass."""
import re
from common import *

def parse(desc,nfc):
    s=desc.lower().replace(',','.').replace('μg','mcg').replace('µg','mcg')
    pack=re.search(r'#\s*(\d+)',s) or re.search(r'pack of\s*(\d+)',s) or re.search(r'(\d+)\s*(?:tablets|tabs|capsules)\b',s)
    strengths=list(re.finditer(r'(\d+(?:\.\d+)?)\s*(mcg|mg|g)\b',s))
    valid=[]; conc=False
    for match in strengths:
        prefix=s[max(0,match.start()-16):match.start()]
        suffix=s[match.end():match.end()+12]
        if re.search(r'(tube|flask|bottle|pack|sachet)\s*$',prefix): continue
        if re.match(r'\s*/\s*(?:\d+(?:\.\d+)?\s*)?(ml|l|g)',suffix): conc=True; continue
        valid.append(match)
    match=valid[0] if len(valid)==1 and not conc and not re.search(r'\d\s*\+\s*\d',s) else None
    value=float(match[1]) if match else np.nan; unit=match[2] if match else ''
    mg=value*{'mcg':.001,'mg':1,'g':1000}.get(unit,1)
    form=next((v for k,v in [('Oral Solid','Oral solid'),('Oral Liquid','Oral liquid'),('Parenteral','Parenteral'),('Lung','Respiratory'),('Nasal','Respiratory'),('Ophthalmic','Ophthalmic'),('Topical','Topical')] if k in nfc),'Other')
    # Topical/liquid grams often encode total container mass; exclude from comparable strength.
    if form in ['Topical','Oral liquid','Other'] and unit=='g': value=mg=np.nan;unit=''
    return dict(strength_value=value,strength_unit=unit,strength_mg=mg,pack_size=float(pack[1]) if pack else np.nan,dosage_form=form,
                concentration_flag=conc,multi_strength_flag=len(valid)>1,strength_parse_status='single_mass' if np.isfinite(mg) else 'not_comparable_or_missing')

def main():
    m,y=load(); attrs=pd.DataFrame([parse(a,b) for a,b in zip(m.Description,m.NFC)])
    m=pd.concat([m,attrs],axis=1); m.to_parquet(PROC/'sku_attributes.parquet',index=False)
    save(m,'sku_attributes')
    save(pd.DataFrame({'attribute':['strength_mg','pack_size','dosage_form'],'coverage':[m.strength_mg.notna().mean(),m.pack_size.notna().mean(),(m.dosage_form!='Other').mean()]}),'attribute_parse_coverage')
if __name__=='__main__': main()
