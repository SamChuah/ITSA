# ITSA: An Information-Theoretic Approach to Automatic Shortcut Avoidance and Domain Generalization in Stereo Matching Networks

This is the official code of the work ITSA: An Information-Theoretic Approach to Automatic Shortcut Avoidance and Domain Generalization in Stereo Matching Networks.

# How to use:
## Environment setup
* Python 3.8
* PyTorch 1.9.0

## :package: Dataset
* [KITTI 2015](http://www.cvlibs.net/datasets/kitti/eval_scene_flow.php?benchmark=stereo)
* [Scene Flow](https://lmb.informatik.uni-freiburg.de/resources/datasets/SceneFlowDatasets.en.html)
* [Middlebury](https://vision.middlebury.edu/stereo/data/)
* [ETH3D](https://www.eth3d.net/datasets)

## :clock4: Training
Run `bash script/train.sh` for training.
### Arguments 
* `itsa`: Path to the pre-trained weight file that you wish to load to the model during training
* `model`: Select the stereo matching networks from one of the following: [PSMNet, GwcNet, CFNet].
* `lambd`: Hyperparameter for our Fisher loss.
* `maxdisp`: Range of disparity. Default = 192.
* `epochs`: Total number of training epochs.
* `eps`: Shortcut-perturbation augmentation strength. 

## :memo: Inference
Run `bash eval_kitti.sh` for inference. Predicted disparity maps for the chosen dataset will be saved to the directory set in the argument `savepath`.
### Arguments 
* `loadmodel`: Path to the pre-trained weight file that you wish to load to the model during training. If directory, all checkpoints will be used for evaluation in loops. 
* `savepath`: Path to save the estimated disparity maps. If None, nothing will be saved.
* `datapath`: Path to the selected data. Make sure you have downloaded and extracted the required dataset to a specific location in your local machine.
* `model`: Select the stereo matching networks from one of the following: [PSMNet, GwcNet, CFNet].
* Select the domain you want to evaluate accordingly [kitti15, kitti12, midFull, midHalf, midQuar, eth] (see below)

#### Example
To run inference using KITTI 2015 dataset and PSMNet, run the following command:
```
python infer.py --model PSMNet \
                --savepath {path_to_save_images} \
                --loadmodel {path_to_pretrained_weights}\
                --kitti15 {change this to the desired dataset}
```
Make sure the directory to the datasets are correct.

## Pretrained Weights [Coming soon...]
* [KITTI 2015](*)
* [DrivingStereo](*)
* [Scene Flow](*)


# Acknowledgement
The codes in this work heavily relies on codes by [PSMNet](https://github.com/JiaRenChang/PSMNet), [GwcNet](https://github.com/xy-guo/GwcNet) and [CFNet](https://github.com/gallenszl/CFNet). We thank the original authors for their awesome repos.
