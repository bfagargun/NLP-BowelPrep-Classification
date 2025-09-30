# NLP-BowelPrep-Classification

Reproducible **NLP pipeline** to classify colonoscopy reports into  
**Good / Intermediate / Poor** bowel preparation quality.  

The workflow combines **TF–IDF features + Logistic Regression** with simple  
**rule-based overrides**, and was validated on >11,000 **Turkish free-text colonoscopy reports**.

---

## How it Works

1. **Training**
   - Input: ~1000 manually labeled colonoscopy reports  
   - Required columns (originally in Turkish):  
     - `cleanliness_phrase` (*temizlik ifadesi*) → short phrase such as *“Kolon temizliği yeterliydi”*  
     - `cleanliness_class` (*temizlik sinifi iyi, orta, kötü*) → gold label (`Good`, `Intermediate`, `Poor`)  
   - Model: TF–IDF (1–3 word n-grams) + Logistic Regression  
   - 5-fold CV accuracy: **~92–94%**

2. **Prediction**
   - Input: full cohort file with long free-text reports  
   - Required column:  
     - `report_text` (*BULGULAR*) → the colonoscopy report body (in Turkish)  
   - Segment extraction: detect *“Kolon temizliği…”* sentence  
   - Apply model + overrides:
     - Contains *“yeterli”* (adequate) without *“yetersiz / değil”* → **Good**  
     - Contains *“yetersiz”* or *“yeterli değil/değildi”* → **Poor**  
     - Contains *“suboptimal / kısmen / yer yer”* → **Intermediate**  
     - Else → model prediction

3. **Output**
   - `colon_cleanliness_model.pkl` → trained logistic regression model  
   - `adr.v3.xlsx` → full dataset with new column `cleanliness_class_pred`  
   - Markdown table with distribution + precision/recall (ready for slides)

---

## Example Results

| Category     | Value / N       | Precision | Recall |
|--------------|-----------------|-----------|--------|
| Good         | 5682 (49.9%)    | 0.99      | 0.99   |
| Intermediate | 2240 (19.7%)    | 0.87      | 0.88   |
| Poor         | 3452 (30.4%)    | 0.88      | 0.88   |

---

## Usage

1. Clone this repository:
   ```bash
   git clone https://github.com/bfagargun/NLP-BowelPrep-Classification.git
   cd NLP-BowelPrep-Classification
   ```
2. Install requirements:
   ```bash
   pip install -r requirements.txt
   ```
3. Adjust file paths in the notebook:
   ```bash
   TRAIN_PATH → your ~1000 labeled dataset
   PREDICT_PATH → your full cohort dataset
   ```
4. Run the notebook: the model is trained, evaluated, and applied to all reports.

## Repository Structure
```bash
.
├── notebook/
│   └── ADR_cleanliness_pipeline.ipynb   # main pipeline
├── examples/
│   └── dummy_training.xlsx              # toy dataset (Turkish free-text, no PHI)
├── requirements.txt
└── README.md
```
## License
This project is released under the MIT License.
Free to use, modify, and share with attribution.
Note: No patient-identifiable data is included.
The example texts are synthetic Turkish free-text colonoscopy reports.

## Citation

If you use this repository in your research, please cite as:

Besim Fazıl Ağargün. *NLP-BowelPrep-Classification: Reproducible NLP pipeline for bowel preparation quality in colonoscopy reports.*  
GitHub repository: https://github.com/bfagargun/NLP-BowelPrep-Classification

### Example BibTeX

```bibtex
@misc{Agargun2025BowelPrep,
  author       = {Ağargün, Besim Fazıl},
  title        = {NLP-BowelPrep-Classification: Reproducible NLP pipeline for bowel preparation quality in colonoscopy reports},
  year         = {2025},
  publisher    = {GitHub},
  journal      = {GitHub repository},
  howpublished = {\url{https://github.com/bfagargun/NLP-BowelPrep-Classification}}
}
```

## Contact

Besim Fazıl Ağargün, MD Istanbul University, Istanbul Faculty of Medicine, Gastroenterology

---
