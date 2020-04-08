import tensor as pz


def compute_iou(box, boxes):
    """Calculates the intersection over union between 'box' and all 'boxes'

    The variables 'box' and 'boxes' contain the corner coordinates
    of the left-top corner (x_min, y_min) and the right-bottom (x_max, y_max)
    corner.

    # Arguments
        box: Numpy array with length at least of 4.
        box_B: Numpy array with shape (num_boxes, 4)

    # Returns
        Numpy array of shape (num_boxes, 1)
    """

    x_min_A, y_min_A, x_max_A, y_max_A = box[:4]
    x_min_B, y_min_B = boxes[:, 0], boxes[:, 1]
    x_max_B, y_max_B = boxes[:, 2], boxes[:, 3]
    # calculating the intersection
    inner_x_min = pz.maximum(x_min_B, x_min_A)
    inner_y_min = pz.maximum(y_min_B, y_min_A)
    inner_x_max = pz.minimum(x_max_B, x_max_A)
    inner_y_max = pz.minimum(y_max_B, y_max_A)
    inner_w = pz.maximum((inner_x_max - inner_x_min), 0)
    inner_h = pz.maximum((inner_y_max - inner_y_min), 0)
    intersection_area = inner_w * inner_h
    # calculating the union
    box_area_B = (x_max_B - x_min_B) * (y_max_B - y_min_B)
    box_area_A = (x_max_A - x_min_A) * (y_max_A - y_min_A)
    union_area = box_area_A + box_area_B - intersection_area
    intersection_over_union = intersection_area / union_area
    return intersection_over_union


def compute_ious(boxes_A, boxes_B):
    """Calculates the intersection over union between 'boxes_A' and 'boxes_B'

    For each box present in the rows of 'boxes_A' it calculates
    the intersection over union with respect to all boxes in 'boxes_B'.

    The variables 'boxes_A' and 'boxes_B' contain the corner coordinates
    of the left-top corner (x_min, y_min) and the right-bottom (x_max, y_max)
    corner.

    # Arguments
        boxes_A: Numpy array with shape (num_boxes_A, 4)
        boxes_B: Numpy array with shape (num_boxes_B, 4)

    # Returns
        Numpy array of shape (num_boxes_A, num_boxes_B)
    """
    IOUs = pz.zeros(len(boxes_A), len(boxes_B))
    for box_A_arg, box_A in enumerate(boxes_A):
        IOUs[box_A_arg, :] = compute_iou(box_A, boxes_B)
    return IOUs


def to_point_form(boxes):
    """Transform from center coordinates to corner coordinates.

    # Arguments
        boxes: Numpy array with shape (num_boxes, 4)

    # Returns
        Numpy array with shape (num_boxes, 4).
    """
    center_x, center_y = boxes[:, 0], boxes[:, 1]
    width, height = boxes[:, 2], boxes[:, 3]
    x_min = center_x - (width / 2.0)
    x_max = center_x + (width / 2.0)
    y_min = center_y - (height / 2.0)
    y_max = center_y + (height / 2.0)
    return pz.concatenate([x_min[:, None], y_min[:, None],
                           x_max[:, None], y_max[:, None]], axis=1)


def to_center_form(boxes):
    """Transform from corner coordinates to center coordinates.

    # Arguments
        boxes: Numpy array with shape (num_boxes, 4)

    # Returns
        Numpy array with shape (num_boxes, 4).
    """
    x_min, y_min = boxes[:, 0], boxes[:, 1]
    x_max, y_max = boxes[:, 2], boxes[:, 3]
    center_x = (x_max + x_min) / 2.
    center_y = (y_max + y_min) / 2.
    width = x_max - x_min
    height = y_max - y_min
    return pz.concatenate([center_x[:, None], center_y[:, None],
                           width[:, None], height[:, None]], axis=1)


def encode(matched, priors, variances):
    """Encode the variances from the priorbox layers into the ground truth boxes
    we have matched (based on jaccard overlap) with the prior boxes.

    # Arguments
        matched: Numpy array of shape (num_priors, 4) with boxes in point-form
        priors: Numpy array of shape (num_priors, 4) with boxes in center-form
        variances: (list[float]) Variances of priorboxes

    # Returns
        encoded boxes: Numpy array of shape (num_priors, 4)
    """

    # dist b/t match center and prior's center
    g_cxcy = (matched[:, :2] + matched[:, 2:4]) / 2.0 - priors[:, :2]
    # encode variance
    g_cxcy /= (variances[0] * priors[:, 2:4])
    # match wh / prior wh
    g_wh = (matched[:, 2:4] - matched[:, :2]) / priors[:, 2:4]
    g_wh = pz.log(pz.abs(g_wh) + 1e-4) / variances[1]
    # return target for smooth_l1_loss
    return pz.concatenate([g_cxcy, g_wh, matched[:, 4:]], 1)  # [num_priors,4]


def decode(predictions, priors, variances):
    """Decode default boxes into the ground truth boxes

    # Arguments
        loc: Numpy array of shape (num_priors, 4)
        priors: Numpy array of shape (num_priors, 4)
        variances: (list[float]) Variances of priorboxes

    # Returns
        decoded boxes: Numpy array of shape (num_priors, 4)
    """

    boxes = pz.concatenate((
        priors[:, :2] + predictions[:, :2] * variances[0] * priors[:, 2:4],
        priors[:, 2:4] * pz.exp(predictions[:, 2:4] * variances[1])), 1)
    boxes[:, :2] = boxes[:, :2] - (boxes[:, 2:4] / 2.0)
    boxes[:, 2:4] = boxes[:, 2:4] + boxes[:, :2]
    return pz.concatenate([boxes, predictions[:, 4:]], 1)
    return boxes


def reversed_argmax(array, axis):
    """Performs the function of torch.max().
    In case of multiple occurrences of the maximum values, the indices
    corresponding to the last occurrence are returned.

    # Arguments:
        array : Numpy array
        axis : int, argmax operation along this specified axis
    # Returns: index_array : Numpy array of ints
    """
    array_flip = pz.flip(array, axis=axis)
    return array.shape[axis] - pz.argmax(array_flip, axis=axis) - 1


def match(boxes, prior_boxes, iou_threshold=0.5):
    """Matches each prior box with a ground truth box (box from ``boxes``).
    It then selects which matched box will be considered positive e.g. iou > .5
    and returns for each prior box a ground truth box that is either positive
    (with a class argument different than 0) or negative.
    # Arguments
        boxes: Numpy array of shape (num_ground_truh_boxes, 4 + 1),
            where the first the first four coordinates correspond to point
            form box coordinates and the last coordinates is the class
            argument. This boxes should be the ground truth boxes.
        prior_boxes: Numpy array of shape (num_prior_boxes, 4).
            where the four coordinates are in center form coordinates.
        iou_threshold: Float between [0, 1]. Intersection over union
            used to determine which box is considered a positive box.
    # Returns
        numpy array of shape (num_prior_boxes, 4 + 1).
            where the first the first four coordinates correspond to point
            form box coordinates and the last coordinates is the class
            argument.
    """
    ious = compute_ious(boxes, to_point_form(pz.float32(prior_boxes)))
    best_box_iou_per_prior_box = pz.max(ious, axis=0)

    best_box_arg_per_prior_box = reversed_argmax(ious, 0)
    best_prior_box_arg_per_box = reversed_argmax(ious, 1)

    best_box_iou_per_prior_box[best_prior_box_arg_per_box] = 2
    # overwriting best_box_arg_per_prior_box if they are the best prior box
    for box_arg in range(len(best_prior_box_arg_per_box)):
        best_prior_box_arg = best_prior_box_arg_per_box[box_arg]
        best_box_arg_per_prior_box[best_prior_box_arg] = box_arg
    matches = boxes[best_box_arg_per_prior_box]
    # setting class value to 0 (background argument)
    matches[best_box_iou_per_prior_box < iou_threshold, 4] = 0
    return matches


def to_one_hot(class_indices, num_classes):
    """ Transform from class index to one-hot encoded vector.

    # Arguments
        class_indices: Numpy array. One dimensional array specifying
            the index argument of the class for each sample.
        num_classes: Integer. Total number of classes.

    # Returns
        Numpy array with shape (num_samples, num_classes).
    """
    one_hot_vectors = pz.zeros((len(class_indices), num_classes))
    for vector_arg, class_args in enumerate(class_indices):
        one_hot_vectors[vector_arg, class_args] = 1.0
    return one_hot_vectors


def substract_mean(image_array, mean):
    """ Subtracts image with channel-wise values.
    # Arguments
        image_array: Numpy array with shape (height, width, 3)
        mean: Numpy array of 3 floats containing the values to be subtracted
            to the image on each corresponding channel.
    """
    image_array = image_array.astype(pz.float32)
    image_array[:, :, 0] -= mean[0]
    image_array[:, :, 1] -= mean[1]
    image_array[:, :, 2] -= mean[2]
    return image_array


def denormalize_keypoints(keypoints, height, width):
    """Transform normalized keypoint coordinates into image coordinates
    # Arguments
        keypoints: Numpy array of shape (num_keypoints, 2)
        height: Int. Height of the image
        width: Int. Width of the image
    """
    for keypoint_arg, keypoint in enumerate(keypoints):
        x, y = keypoint[:2]
        # transform key-point coordinates to image coordinates
        x = (min(max(x, -1), 1) * width / 2 + width / 2) - 0.5
        # flip since the image coordinates for y are flipped
        y = height - 0.5 - (min(max(y, -1), 1) * height / 2 + height / 2)
        x, y = int(round(x)), int(round(y))
        keypoints[keypoint_arg][:2] = [x, y]
    return keypoints


def normalize_keypoints(keypoints, height, width):
    """Transform keypoints in image coordinates to normalized coordinates
        keypoints: Numpy array of shape (num_keypoints, 2)
        height: Int. Height of the image
        width: Int. Width of the image
    """
    normalized_keypoints = pz.zeros_like(keypoints, dtype=pz.float32)
    for keypoint_arg, keypoint in enumerate(keypoints):
        x, y = keypoint[:2]
        # transform key-point coordinates to image coordinates
        x = (((x + 0.5) - (width / 2.0)) / (width / 2))
        y = (((height - 0.5 - y) - (height / 2.0)) / (height / 2))
        normalized_keypoints[keypoint_arg][:2] = [x, y]
    return normalized_keypoints


def make_box_square(box, offset_scale=0.05):
    """Makes box coordinates square.

    # Arguments
        box: Numpy array with shape (4) with point corner coordinates.
        offset_scale: Float, scale of the addition applied box sizes.

    # Returns
        returns: List of box coordinates ints.
    """

    x_min, y_min, x_max, y_max = box[:4]
    center_x = (x_max + x_min) / 2.0
    center_y = (y_max + y_min) / 2.0
    width = x_max - x_min
    height = y_max - y_min

    if height >= width:
        half_box = height / 2.0
        x_min = center_x - half_box
        x_max = center_x + half_box
    if width > height:
        half_box = width / 2.0
        y_min = center_y - half_box
        y_max = center_y + half_box

    box_side_lenght = (x_max + x_min) / 2.0
    offset = offset_scale * box_side_lenght
    x_min = x_min - offset
    x_max = x_max + offset
    y_min = y_min - offset
    y_max = y_max + offset
    return (int(x_min), int(y_min), int(x_max), int(y_max))


def apply_offsets(coordinates, offset_scales):
    """Apply offsets to coordinates
    #Arguments
        coordinates: List of floats containing coordinates in point form.
        offset_scales: List of floats having x and y scales respectively.
    #Returns
        coordinates: List of floats containing coordinates in point form.
    """
    x_min, y_min, x_max, y_max = coordinates
    x_offset_scale, y_offset_scale = offset_scales
    x_offset = (x_max - x_min) * x_offset_scale
    y_offset = (y_max - y_min) * y_offset_scale
    x_min = int(x_min - x_offset)
    y_max = int(y_max + x_offset)
    y_min = int(y_min - y_offset)
    x_max = int(x_max + y_offset)
    return (x_min, y_min, x_max, y_max)


