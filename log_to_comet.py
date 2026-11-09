"""Upload training results of both models to Comet (retrospective logging).

The numbers come from the training logs printed in Colab. They are uploaded
after training, not streamed live.
"""
import os

from comet_ml import Experiment

PROJECT = "signature-app"

# ---------------- Detection (YOLOX-S) ----------------
det_train = [3.746, 2.739, 2.393, 2.211, 2.094, 1.970, 1.904, 1.810, 1.712, 1.633,
             1.536, 1.454, 1.373, 1.295, 1.216, 1.155, 1.092, 1.048, 1.008, 0.989]
det_val = [9.109, 2.894, 2.813, 3.036, 2.120, 2.192, 2.369, 3.132, 3.048, 1.811,
           1.599, 2.061, 1.546, 1.472, 1.387, 1.373, 1.311, 1.259, 1.250, 1.236]

det = Experiment(
    project_name=PROJECT,
    auto_metric_logging=False,
    auto_param_logging=False,
)
det.set_name("detection-yolox-s")
det.add_tags(["detection", "retrospective"])
det.log_parameters({
    "model": "YOLOX-S",
    "epochs": 20,
    "iters_per_epoch": 832,
    "input_size": 416,
    "early_stopping_patience": 5,
})
for epoch, (tr, va) in enumerate(zip(det_train, det_val)):
    det.log_metric("train/loss", tr, epoch=epoch, step=epoch)
    det.log_metric("val/loss", va, epoch=epoch, step=epoch)
det.log_metric("mAP50", 0.9478622078895569)
det.log_metric("mAP50-95", 0.825051486492157)
det.log_other("note", "Epoch losses uploaded after training from the Colab log. "
                      "mAP is the final evaluation only (not per epoch).")
det.end()

# ---------------- Similarity (ResNet18) ----------------
sim_loss = [0.0964, 0.0431, 0.0255, 0.0180, 0.0142, 0.0134]
sim_val_auc = [0.9369, 0.9483, 0.9468, 0.9494, 0.9447, 0.9478]
sim_hard_auc = [0.9083, 0.9197, 0.9175, 0.9191, 0.9139, 0.9193]

sim = Experiment(
    project_name=PROJECT,
    auto_metric_logging=False,
    auto_param_logging=False,
)
sim.set_name("similarity-resnet18")
sim.add_tags(["similarity", "retrospective"])
sim.log_parameters({
    "model": "ResNet18 embedding",
    "epochs": 6,
    "images": 15394,
    "signers": 379,
    "signers_train": 265,
    "signers_val": 56,
    "signers_test": 58,
})
for i, (l, a, h) in enumerate(zip(sim_loss, sim_val_auc, sim_hard_auc), start=1):
    sim.log_metric("train/loss", l, epoch=i, step=i)
    sim.log_metric("val/AUC", a, epoch=i, step=i)
    sim.log_metric("val/hard_forged_AUC", h, epoch=i, step=i)
sim.log_metric("test/AUC", 0.9406)
sim.log_metric("test/hard_forged_AUC", 0.9073)
sim.log_metric("EER", 0.1171)
sim.log_metric("threshold", 0.487)
sim.log_metric("onnx_vs_pytorch_max_diff", 1.937151e-07)
sim.log_other("note", "Epoch metrics uploaded after training from the Colab log.")
sim.end()

print("Done. Open comet.com, project:", PROJECT)