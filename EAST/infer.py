import os
import torch
import cv2
import numpy as np
import time
import warnings
import config as cfg
from model import East
import utils

# Suppress warnings
warnings.filterwarnings("ignore")

def predict(image_path, model_checkpoint):
    # Load image
    # im = cv2.imread(image_path)
    im = cv2.imread(image_path)[:, :, ::-1]

    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")

    # Initialize the EAST model and load checkpoint
    model = East(device)
    model = torch.nn.DataParallel(model, device_ids=cfg.gpu_ids)

    # Load the model checkpoint with weights_only=True
    checkpoint = torch.load(model_checkpoint, map_location=torch.device(device), weights_only=True)
    model.load_state_dict(checkpoint['state_dict'])
    model.eval()

    # Resize image and convert to tensor format
    im_resized, (ratio_h, ratio_w) = utils.resize_image(im)
    im_resized = im_resized.astype(np.float32).transpose(2, 0, 1)
    im_tensor = torch.from_numpy(im_resized).unsqueeze(0).cpu()

    # Inference
    timer = {'net': 0, 'restore': 0, 'nms': 0}
    start = time.time()
    score, geometry = model(im_tensor)
    timer['net'] = time.time() - start

    # Process output
    score = score.permute(0, 2, 3, 1).data.cpu().numpy()
    geometry = geometry.permute(0, 2, 3, 1).data.cpu().numpy()
    
    # Detect boxes
    boxes, timer = utils.detect(
        score_map=score, geo_map=geometry, timer=timer,
        score_map_thresh=cfg.score_map_thresh, box_thresh=cfg.box_thresh,
        nms_thres=cfg.box_thresh
    )
    bbox_result_dict = {'detections': []}

    # Parse detected boxes and adjust coordinates
    if boxes is not None:
        boxes = boxes[:, :8].reshape((-1, 4, 2))
        boxes[:, :, 0] /= ratio_w
        boxes[:, :, 1] /= ratio_h
        for box in boxes:
            box = utils.sort_poly(box.astype(np.int32))
            if np.linalg.norm(box[0] - box[1]) < 5 or np.linalg.norm(box[3] - box[0]) < 5:
                continue
            bbox_result_dict['detections'].append([
                [int(coord[0]), int(coord[1])] for coord in box
            ])

    return bbox_result_dict

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description='Text detection using EAST model')
    parser.add_argument('--image_path', type=str, required=True, help='Path to the input image')
    parser.add_argument('--model_checkpoint', type=str, required=True, help='Path to the model checkpoint file')
    args = parser.parse_args()

    # Run prediction and get results as dictionary
    detection_result = predict(args.image_path, args.model_checkpoint)
    print(detection_result)
