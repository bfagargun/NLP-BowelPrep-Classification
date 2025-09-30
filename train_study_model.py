# -*- coding: utf-8 -*-
"""
Train TF-IDF (word 1-3) + Logistic Regression (C=4.0, class_weight='balanced')
on the labeled dataset and save 'colon_cleanliness_model.pkl'.

This script reproduces the model used in the study.
"""
import argparse, unicodedata, joblib
import pandas as pd
from sklearn.model_selection import StratifiedKFold, cross_val_predict
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import Pipeline
from sklearn.metrics import classification_report, accuracy_score

def normalize(text):
    if not isinstance(text, str):
        return ''
    return ''.join(c for c in unicodedata.normalize('NFKD', text) if not unicodedata.combining(c)).lower()

def main(args):
    df = pd.read_excel(args.train, engine='openpyxl').dropna(subset=[args.text_col, args.label_col])
    X  = df[args.text_col].astype(str).map(normalize)
    y  = df[args.label_col].astype(str).str.strip().str.lower()

    pipe = Pipeline([
        ('tfidf', TfidfVectorizer(analyzer='word', ngram_range=(1,3), min_df=2, max_df=0.95)),
        ('clf', LogisticRegression(C=4.0, class_weight='balanced', max_iter=3000, solver='lbfgs', random_state=42)),
    ])

    skf  = StratifiedKFold(n_splits=5, shuffle=True, random_state=42)
    yhat = cross_val_predict(pipe, X, y, cv=skf, method='predict')
    print('=== Cross-validation on TRAIN ===')
    print('Accuracy:', accuracy_score(y, yhat))
    print(classification_report(y, yhat, digits=2))

    pipe.fit(X, y)
    joblib.dump(pipe, args.out_model)
    print('Model saved to:', args.out_model)

if __name__ == '__main__':
    p = argparse.ArgumentParser()
    p.add_argument('--train',     required=True)  # e.g. C:\...\ADR.v2.xlsx
    p.add_argument('--text-col',  default='temizlik ifadesi')
    p.add_argument('--label-col', default='temizlik sinifi iyi, orta, kötü')
    p.add_argument('--out-model', required=True)  # e.g. C:\...\colon_cleanliness_model.pkl
    main(p.parse_args())
