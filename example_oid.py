# coding: utf-8
__author__ = 'ZFTurbo: https://kaggle.com/zfturbo'


import os
import time
import pickle
import numpy as np
import pandas as pd
from multiprocessing import Pool, cpu_count
from itertools import repeat
from ensemble_boxes import *
from map_boxes import *
import json

label_names = ['holothurian', 'echinus', 'scallop', 'starfish']

def read_json(path):
    with open(path,'r') as load_f:
        load_dict = json.load(load_f)
    return load_dict

def get_ann(ann):
    anns = ann['annotations'] # list[{"image_id":image_id, "bbox":[x, y, w, h], "category_id": category_id,}, {}]
    # ['ImageId', 'LabelName', 'XMin', 'XMax', 'YMin', 'YMax']
    ImageID = []
    LabelName = []
    XMin = []
    XMax = []
    YMin = []
    YMax = []
    for j in range(len(anns)):
        id = anns[j]['image_id']
        category_id = anns[j]['category_id']
        category = label_names[int(category_id)-1]
        bbox = anns[j]['bbox']
        x1 = bbox[0]
        y1 = bbox[1]
        x2 = bbox[2] + bbox[0] - 1
        y2 = bbox[3] + bbox[1] - 1
        ImageID.append(id)
        LabelName.append(category)
        #Conf.append(float(preds[j]['score']))
        XMin.append(float(x1))
        XMax.append(float(y1))
        YMin.append(float(x2))
        YMax.append(float(y2))

    res = pd.DataFrame(ImageID, columns=['ImageId'])
    res['LabelName'] = LabelName
    #res['Conf'] = Conf
    res['XMin'] = XMin
    res['XMax'] = XMax
    res['YMin'] = YMin
    res['YMax'] = YMax

    return res

def save_in_file_fast(arr, file_name):
    pickle.dump(arr, open(file_name, 'wb'))


def load_from_file_fast(file_name):
    return pickle.load(open(file_name, 'rb'))

def compact_per_im(data_frame): ## data_frame == get_detections(...)
    ann = data_frame
    al_id = ann['ImageId'].values.tolist()
    im_id = sorted(set(al_id),key=al_id.index)
    al_l = ann.values.tolist()
    string = []
    for i in im_id:
        row = []
        c = 0
        # print(1)
        for j in al_l:
            # print(len(al_l))
            if j[0] == i:
                al_l = al_l[1:]
                # print(len(al_l))
                s = [str(m) for m in j]
                js = " ".join(s[1:])
                print(j)
                print(i)
                row.append(js)
            else:
                print('skip')
                break
        rows = " ".join(row)
        string.append(rows)
    res = pd.DataFrame(im_id, columns=['ImageId'])
    res['PredictionString'] = string
    return res

def get_detections_old(path): ## with PredictionString per im
    preds = pd.read_csv(path)
    ids = preds['ImageId'].values
    preds_strings = preds['PredictionString'].values

    ImageID = []
    LabelName = []
    Conf = []
    XMin = []
    XMax = []
    YMin = []
    YMax = []
    for j in range(len(ids)):
        # print('Go for {}'.format(ids[j]))
        id = ids[j]
        if str(preds_strings[j]) == 'nan':
            continue
        arr = preds_strings[j].strip().split(' ')
        if len(arr) % 6 != 0:
            print('Some problem here! {}'.format(id))
            exit()
        for i in range(0, len(arr), 6):
            ImageID.append(id)
            LabelName.append(arr[i])
            Conf.append(float(arr[i + 1]))
            XMin.append(float(arr[i + 2]))
            XMax.append(float(arr[i + 4]))
            YMin.append(float(arr[i + 3]))
            YMax.append(float(arr[i + 5]))

    res = pd.DataFrame(ImageID, columns=['ImageId'])
    res['LabelName'] = LabelName
    res['Conf'] = Conf
    res['XMin'] = XMin
    res['XMax'] = XMax
    res['YMin'] = YMin
    res['YMax'] = YMax

    return res
def get_detections(path):
    # preds = pd.read_csv(path)
    # ids = preds['ImageId'].values
    #preds_strings = preds['PredictionString'].values

    preds = read_json(path) #list [{"image_id": 1, "category_id": 1, "bbox": [271.98, 346.4, 45.46, 58.88], "score": 0.49}, ]
    ImageID = []
    LabelName = []
    Conf = []
    XMin = []
    XMax = []
    YMin = []
    YMax = []
    for j in range(len(preds)):
        # print('Go for {}'.format(ids[j]))
        #if str(preds_strings[j]) == 'nan':
         #   continue
        #arr = preds_strings[j].strip().split(' ')
        #if len(arr) % 6 != 0:
         #   print('Some problem here! {}'.format(id))
          #  exit()
        #for i in range(0, len(arr), 6):
        id = preds[j]['image_id']
        category_id = preds[j]['category_id']
        category = label_names[int(category_id)-1]
        bbox = preds[j]['bbox']
        x1 = bbox[0]
        y1 = bbox[1]
        x2 = bbox[2] + bbox[0] - 1
        y2 = bbox[3] + bbox[1] - 1
        ImageID.append(id)
        LabelName.append(category)
        Conf.append(float(preds[j]['score']))
        XMin.append(float(x1))
        XMax.append(float(y1))
        YMin.append(float(x2))
        YMax.append(float(y2))

    res = pd.DataFrame(ImageID, columns=['ImageId'])
    res['LabelName'] = LabelName
    res['Conf'] = Conf
    res['XMin'] = XMin
    res['XMax'] = XMax
    res['YMin'] = YMin
    res['YMax'] = YMax

    return res


def process_single_id(id, res, im_hw, weights, params):
    run_type = params['run_type']
    verbose = params['verbose']

    if verbose:
        print('Go for ID: {}'.format(id))
    boxes_list = []
    scores_list = []
    labels_list = []
    labels_to_use_forward = dict()
    labels_to_use_backward = dict()

    for i in range(len(res[id])):
        boxes = []
        scores = []
        labels = []

        dt = res[id][i]
        if str(dt) == 'nan':
            boxes = np.zeros((0, 4), dtype=np.float32)
            scores = np.zeros((0, ), dtype=np.float32)
            labels = np.zeros((0, ), dtype=np.int32)
            boxes_list.append(boxes)
            scores_list.append(scores)
            labels_list.append(labels)
            continue

        pred = dt.strip().split(' ')

        # Empty preds
        if len(pred) <= 1:
            boxes = np.zeros((0, 4), dtype=np.float32)
            scores = np.zeros((0,), dtype=np.float32)
            labels = np.zeros((0,), dtype=np.int32)
            boxes_list.append(boxes)
            scores_list.append(scores)
            labels_list.append(labels)
            continue

        # Check correctness
        if len(pred) % 6 != 0:
            print('Erorr % 6 {}'.format(len(pred)))
            print(dt)
            exit()

        for j in range(0, len(pred), 6):
            lbl = pred[j]
            scr = float(pred[j + 1])
            box_x1 = float(pred[j + 2])
            box_y1 = float(pred[j + 3])
            box_x2 = float(pred[j + 4])
            box_y2 = float(pred[j + 5])

            if box_x1 >= box_x2:
                if verbose:
                    print('Problem with box x1 and x2: {}. Skip it'.format(pred[j:j+6]))
                continue
            if box_y1 >= box_y2:
                if verbose:
                    print('Problem with box y1 and y2: {}. Skip it'.format(pred[j:j+6]))
                continue
            if scr <= 0:
                if verbose:
                    print('Problem with box score: {}. Skip it'.format(pred[j:j+6]))
                continue

            boxes.append([box_x1, box_y1, box_x2, box_y2])
            scores.append(scr)
            if lbl not in labels_to_use_forward:
                cur_point = len(labels_to_use_forward)
                labels_to_use_forward[lbl] = cur_point
                labels_to_use_backward[cur_point] = lbl
            labels.append(labels_to_use_forward[lbl])

        boxes = np.array(boxes, dtype=np.float32)
        scores = np.array(scores, dtype=np.float32)
        labels = np.array(labels, dtype=np.int32)

        boxes_list.append(boxes)
        scores_list.append(scores)
        labels_list.append(labels)

    # Empty predictions for all models
    if len(boxes_list) == 0:
        return np.array([]), np.array([]), np.array([])

    if run_type == 'wbf':
        merged_boxes, merged_scores, merged_labels = weighted_boxes_fusion(boxes_list, scores_list, labels_list,
                                                                       weights=weights, iou_thr=params['intersection_thr'],
                                                                       skip_box_thr=params['skip_box_thr'],
                                                                           conf_type=params['conf_type'])
    elif run_type == 'nms':
        iou_thr = params['iou_thr']
        merged_boxes, merged_scores, merged_labels = nms(boxes_list, scores_list, labels_list, weights=weights, iou_thr=iou_thr)
    elif run_type == 'soft-nms':
        iou_thr = params['iou_thr']
        sigma = params['sigma']
        thresh = params['thresh']
        merged_boxes, merged_scores, merged_labels = soft_nms(boxes_list, scores_list, labels_list,
                                                              weights=weights, iou_thr=iou_thr, sigma=sigma, thresh=thresh)
    elif run_type == 'nmw':
        merged_boxes, merged_scores, merged_labels = non_maximum_weighted(boxes_list, scores_list, labels_list,
                                                                       weights=weights, iou_thr=params['intersection_thr'],
                                                                       skip_box_thr=params['skip_box_thr'])

    if verbose:
        print(len(boxes_list), len(merged_boxes))
    if 'limit_boxes' in params:
        limit_boxes = params['limit_boxes']
        if len(merged_boxes) > limit_boxes:
            merged_boxes = merged_boxes[:limit_boxes]
            merged_scores = merged_scores[:limit_boxes]
            merged_labels = merged_labels[:limit_boxes]

    # 将坐标还原成实际值
    for i in range(4):
        if i == 0 or i == 2: # xmin, xmax
            merged_boxes[:,i] = merged_boxes[:,i]*im_hw[id][1] 
        else:
            merged_boxes[:,i] = merged_boxes[:,i]*im_hw[id][0] # h
    
    # Rename labels back
    merged_labels_string = []
    for m in merged_labels:
        merged_labels_string.append(labels_to_use_backward[m])
    merged_labels = np.array(merged_labels_string, dtype=np.str)

    # Create IDs array
    ids_list = [id] * len(merged_labels)

    return merged_boxes, merged_scores, merged_labels, ids_list


def ensemble_predictions(pred_filenames, weights, params):
    verbose = False
    if 'verbose' in params:
        verbose = params['verbose']

    start_time = time.time()
    procs_to_use = max(cpu_count() // 2, 1)
    # procs_to_use = 1
    if verbose:
        print('Use processes: {}'.format(procs_to_use))

    res = dict()
    im_hw = dict()
    ref_ids = None
    ref_hw = None
    for j in range(len(pred_filenames)):
        s = pd.read_csv(pred_filenames[j])
        
        s.sort_values('image_id', inplace=True)# 按'imid'列排序，替换原值
        s.reset_index(drop=True, inplace=True)#将索引重置为整型，并舍去
        
        ids = s['image_id'].values
        if ref_ids is None:
            ref_ids = tuple(ids)
        else:
            if ref_ids != tuple(ids):
                print('Different IDs in ensembled CSVs!')
                exit()
                
        hw = s[['im_h', 'im_w']].values
        if ref_hw is None:
            ref_hw = hw
        else:
            if (ref_hw != hw).any():
                print('Different HWs in ensembled CSVs!')
                exit()
                
        preds = s['PredictionString'].values # np_array
        for i in range(len(ids)):
            id = ids[i]
            if id not in res:
                res[id] = []
                im_hw[id] = []
            res[id].append(preds[i])
            if j == 1:
                im_hw[id].append(hw[i,0])
                im_hw[id].append(hw[i,1])

    p = Pool(processes=procs_to_use)
    ids_to_use = sorted(list(res.keys()))
    results = p.starmap(process_single_id, zip(ids_to_use, repeat(res), repeat(im_hw), repeat(weights), repeat(params)))

    all_ids = []
    all_boxes = []
    all_scores = []
    all_labels = []
    for boxes, scores, labels, ids_list in results:
        if boxes is None:
            continue
        all_boxes.append(boxes)
        all_scores.append(scores)
        all_labels.append(labels)
        all_ids.append(ids_list)

    all_ids = np.concatenate(all_ids)
    all_boxes = np.concatenate(all_boxes)
    all_scores = np.concatenate(all_scores)
    all_labels = np.concatenate(all_labels)
    if verbose:
        print(all_ids.shape, all_boxes.shape, all_scores.shape, all_labels.shape)

    res = pd.DataFrame(all_labels, columns=['name'])
    res['image_id'] = all_ids
    res['confidence'] = all_scores
    res['xmin'] = all_boxes[:, 0]
    res['ymin'] = all_boxes[:, 1]
    res['xmax'] = all_boxes[:, 2]    
    res['ymax'] = all_boxes[:, 3]
    if verbose:
        print('Run time: {:.2f}'.format(time.time() - start_time))
    return res
    
    
if __name__ == '__main__':
    if 1:
        params = {
            'run_type': 'nms',
            'iou_thr': 0.5,
            'verbose': True,
        }
    if 1:
        params = {
            'run_type': 'soft-nms',
            'iou_thr': 0.5,
            'thresh': 0.0001,
            'sigma': 0.1,
            'verbose': True,
        }
    if 1:
        params = {
            'run_type': 'nmw',
            'skip_box_thr': 0.000000001,
            'intersection_thr': 0.5,
            'limit_boxes': 30000,
            'verbose': True,
        }
    if 1:
        params = {
            'run_type': 'wbf',
            'skip_box_thr': 0.0000001,
            'intersection_thr': 0.6,
            'conf_type': 'avg',
            'limit_boxes': 30000,
            'verbose': True,
        }
    
    # Files available here: https://github.com/ZFTurbo/Weighted-Boxes-Fusion/releases/download/v1.0/test_data.zip
    
#     annotations_path = '/media/ubuntu/gqp/underwater_od/data/annotations_json/annotations_val.json' # 两者格式不同，分开处理
    pred_list = [
        '/home/gqp/centernet_underwater/CenterNet/exp/ctdet/coco_dla_140epoch_91/result_test-A_flip_multi_scale_coco_dla_140epoch_91.csv',
        '/home/gqp/centernet_underwater/CenterNet/exp/ctdet/coco_hg_140epoch_91/result_test-A_flip_multi_scale_coco_hg_140epoch_91.csv',
    ]
    weights = [1, 1]

    ensemble_preds = ensemble_predictions(pred_list, weights, params)
    ensemble_preds.to_csv("ensemble_91.csv", index=False)
    for i in range(len(pred_list)):
        print("File: {}".format(os.path.basename(pred_list[i])))
    print("Ensemble [{}] Weights: {} Params: {}".format(len(weights), weights, params))

#     ann = pd.read_csv(annotations_path)
#     ann = ann[['ImageId', 'LabelName', 'XMin', 'XMax', 'YMin', 'YMax']].values
    
#     ann = read_json(annotations_path)
#     ann = get_ann(ann)
#     print(ann)
#     ann = ann[['ImageId', 'LabelName', 'XMin', 'XMax', 'YMin', 'YMax']].values

   # Find initial scores
#     for i in range(len(pred_list)):
#         det = get_detections(pred_list[i])
#         print(det)
#         det = det[['ImageId', 'LabelName', 'Conf', 'XMin', 'XMax', 'YMin', 'YMax']].values
#         mean_ap, average_precisions = mean_average_precision_for_boxes(ann, det, verbose=False)
#         print("File: {} mAP: {:.6f}".format(os.path.basename(pred_list[i]), mean_ap))

#     ensemble_preds = ensemble_predictions(pred_list, weights, params)
#     ensemble_preds.to_csv("ensemble.csv", index=False)
#     ensemble_preds = ensemble_preds[['name', 'image_id', 'confidence', 'xmin', 'ymin', 'xmax', 'ymax']].values
#     mean_ap, average_precisions = mean_average_precision_for_boxes(ann, ensemble_preds, verbose=True)
#     print("Ensemble [{}] Weights: {} Params: {} mAP: {:.6f}".format(len(weights), weights, params, mean_ap))
    

