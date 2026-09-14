# Lab 2 — Run comparison

Experiment `itcs355-lab2` · 12 trials · estimated compute cost 2.4231 THB

Cost uses a conservative planning rate, not the final Cloud Billing amount.

`thb_per_point` is cost per percentage point of val_roc_auc above the worst trial. Cheap improvements rank low; expensive improvements rank high, however good the headline number is. The worst trial has no improvement, so its value is undefined.

| run_id   |   val_roc_auc |   est_cost_thb |   n_estimators |   max_depth |   min_samples_leaf |   thb_per_point |
|:---------|--------------:|---------------:|---------------:|------------:|-------------------:|----------------:|
| 5b0573cd |        0.8426 |         0.2    |            100 |           4 |                  5 |          0.1242 |
| f5816abb |        0.8424 |         0.2033 |            100 |           4 |                  1 |          0.1279 |
| 2a29c0f9 |        0.8411 |         0.2    |            300 |           4 |                  5 |          0.137  |
| d4c5e1c8 |        0.8404 |         0.2033 |            300 |           4 |                  1 |          0.1463 |
| 2de1a52a |        0.8397 |         0.2    |            100 |           8 |                  5 |          0.1515 |
| e2ab0fa0 |        0.8377 |         0.2    |            300 |           8 |                  5 |          0.1786 |
| 551a39b2 |        0.8354 |         0.1    |            300 |          12 |                  5 |          0.1124 |
| 3184022c |        0.8338 |         0.3033 |            300 |           8 |                  1 |          0.4155 |
| 01956c2d |        0.8322 |         0.2033 |            100 |          12 |                  5 |          0.3567 |
| 4b79f623 |        0.8312 |         0.2033 |            100 |           8 |                  1 |          0.4326 |
| 2e52496e |        0.8268 |         0.2033 |            100 |          12 |                  1 |          6.7767 |
| 3e8c46b6 |        0.8265 |         0.2033 |            300 |          12 |                  1 |        nan      |

## Selection and justification

เลือก trial 01 (100 trees, max_depth 4, min_samples_leaf 5) จากงาน Spot: validation ROC AUC 0.8426 และ test ROC AUC 0.8533. แม้เป็นคะแนน validation สูงสุด แต่เหนือ trial 00 เพียง 0.00016 ซึ่งเล็กกว่าความผันผวนเมื่อเปลี่ยน seed มาก จึงไม่ถือว่าคะแนนที่ต่างกันนี้พิสูจน์ความเหนือกว่า เลือกรุ่นนี้เพราะใช้ต้นไม้เพียง 100 ต้น ความลึกต่ำ และ leaf 5 ช่วยจำกัดการฟิต noise โดยมีต้นทุนใกล้รุ่นรอง

เมื่อใช้ seed 20260101 (Spot), 20260102 และ 20260103 (ตรวจซ้ำใน WSL) validation AUC เท่ากับ 0.8426, 0.8479, 0.8492; ค่าเฉลี่ย 0.8466 ส่วนเบี่ยงเบนมาตรฐานตัวอย่าง 0.0035. ค่าฝึกประเมิน 0.20 บาทต่อครั้ง หรือราว 0.20 บาทต่อเดือนหากฝึกใหม่เดือนละครั้ง ยังไม่รวม storage, logs และราคาจริงจาก Billing. การเลือกนี้อาจผิดหากข้อมูลเซนเซอร์หรืออัตราเครื่องเสียเปลี่ยนหลังใช้งาน จึงควรติดตาม PR AUC และ data drift.