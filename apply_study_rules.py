# -*- coding: utf-8 -*-
"""
Apply the study's inference procedure:
- Extract a short 'cleanliness' segment from the full report
  (anchor 'kolon temizli...' or first 100 chars; window +100 chars after anchor).
- Predict with the trained model.
- Combine with simple rules on the segment:
  * If model predicts 'orta' -> keep 'orta'
  * If 'yeterli' present without negation/yetersiz -> 'iyi'
  * If 'yetersiz' or 'degil/degildi' -> 'kötü'
  * If 'subopt/kısmen/yer yer/yeryer' -> 'orta'
- Save predictions to Excel.
"""
import argparse, unicodedata, joblib
import pandas as pd
from sklearn.metrics import accuracy_score, classification_report

def normalize(text):
    if not isinstance(text, str):
        return ''
    return ''.join(c for c in unicodedata.normalize('NFKD', text) if not unicodedata.combining(c)).lower()

def extract_segment(text):
    if not isinstance(text, str):
        return ''
    norm = normalize(text)
    anchors = ['kolon temizligi', 'kolon temizlig', 'kolon temizlik', 'kolon temizli']
    idx = -1
    for p in anchors:
        idx = norm.find(p)
        if idx != -1:
            break
    if idx != -1:
        end = norm.find('.', idx)
        if end == -1:
            end = idx + 100  # window +100
        return norm[idx:end]
    return norm[:100]          # fallback: first 100 chars

def classify_final(text, model):
    segment = extract_segment(text)
    norm = segment  # already normalized
    model_pred = model.predict([segment])[0]  # 'iyi'/'orta'/'kötü'
    if model_pred == 'orta':
        return 'orta'
    if 'yeterli' in norm:
        if ('degil' in norm) or ('degildi' in norm) or ('yetersiz' in norm):
            return 'kötü'
        else:
            return 'iyi'
    if ('yetersiz' in norm) or ('degil' in norm) or ('degildi' in norm):
        return 'kötü'
    if ('subopt' in norm) or ('kismen' in norm) or ('kısmen' in norm) or ('yer yer' in norm) or ('yeryer' in norm):
        return 'orta'
    return model_pred

def main(args):
    model = joblib.load(args.model)

    # Optional: evaluate on TRAIN (consistency check)
    if args.train and args.train_text_col and args.train_label_col:
        train_df = pd.read_excel(args.train, engine='openpyxl').dropna(subset=[args.train_text_col, args.train_label_col])
        y_true = train_df[args.train_label_col].astype(str).str.strip().str.lower()
        y_pred = train_df[args.train_text_col].apply(lambda t: classify_final(t, model))
        print('=== Evaluation on TRAIN (study-style) ===')
        print('Accuracy:', accuracy_score(y_true, y_pred))
        print(classification_report(y_true, y_pred, digits=2))

    # Apply to full cohort
    full_df = pd.read_excel(args.predict, engine='openpyxl')
    assert args.full_text_col in full_df.columns, f'Text column not found: {args.full_text_col}'
    full_df['temizlik sinifi tahmin'] = full_df[args.full_text_col].apply(lambda t: classify_final(t, model))

    print('\n=== Distribution on FULL (study-style) ===')
    print(full_df['temizlik sinifi tahmin'].value_counts(dropna=False))

    full_df.to_excel(args.output, index=False)
    print('\nSaved:', args.output)

if __name__ == '__main__':
    p = argparse.ArgumentParser()
    p.add_argument('--model',          required=True)  # e.g. C:\...\colon_cleanliness_model.pkl
    p.add_argument('--predict',        required=True)  # e.g. C:\...\tum_hastalar_with_bulgular_v2.xlsx
    p.add_argument('--output',         required=True)  # e.g. C:\...\adr.v3.xlsx
    p.add_argument('--full-text-col',  default='BULGULAR')
    # optional evaluation on TRAIN
    p.add_argument('--train',          default=None)   # e.g. C:\...\ADR.v2.xlsx
    p.add_argument('--train-text-col', default='temizlik ifadesi')
    p.add_argument('--train-label-col',default='temizlik sinifi iyi, orta, kötü')
    main(p.parse_args())
