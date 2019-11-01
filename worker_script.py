import argparse
from Autozone.find_zones import *
from Autozone.plotting import *
from Autozone.segmentation import *
import os
from skimage import io
import skimage as ski
import pandas as pd


if __name__ == '__main__':
    parser = argparse.ArgumentParser(formatter_class=argparse.ArgumentDefaultsHelpFormatter,
                                     description='Worker script for Autozone')
    parser.add_argument('input_img', type=str,
                        help='Absolute Input TIF image to be zonated, with signal of interest at channel 0, \
                            GS at channel 1 and DAPI at channel 2')
    parser.add_argument('-o', '--output', metavar='O', type=str, nargs='?', default='',
                        help='output folder of results, if not supplied, it will be that same as the input file name.')
    parser.add_argument('-v', '--vessel_size_factor', metavar='V', type=int, nargs='?', default=2,
                        help='Vessel size threshold as x/10000 fold of image size')
    parser.add_argument('-d', '--maximal_neighbor_distance', metavar='D', type=int, nargs='?', default=20,
                        help='maximal pixel distance between two neighboring masks to be considered as two separate masks.')
    parser.add_argument('-gl', '--gs_lower_limit', metavar='L', type=float, nargs='?', default=0.25,
                        help='The lower percentatge limit of GS signal intensity within a mask, which is used in classify CV from PV')
    parser.add_argument('-gh', '--gs_higher_limit', metavar='H', type=float, nargs='?', default=0.75,
                        help='The higher percentatge limit of GS signal intensity within a mask, which is used in classify CV from PV')
    parser.add_argument('-gs', '--gs_step', metavar='S', type=float, nargs='?', default=0.1,
                        help='The interval of percentage in the GS intensity features.')
    args = parser.parse_args()
    input_tif_fn = args.input_img
    output = args.output
    vessel_size_factor = args.vessel_size_factor
    max_dist = args.maximal_neighbor_distance
    gs_low = args.gs_lower_limit
    gs_high = args.gs_higher_limit
    gs_step = args.gs.gs_step

    # os.chdir("/home2/s190548/work_zhu/images/New Tif/Normal  30%")
    # tif_files = sorted([x for x in os.listdir() if ".tif" in x])
    # for input_tif_fn in tif_files:
    output_prefix = input_tif_fn.replace(".tif", "")
    output_mask_fn = output_prefix + " masks.tif"
    print('Prosessing {}'.format(input_tif_fn))
    img = io.imread(input_tif_fn)
    if not os.path.exists(output_prefix):
        os.mkdir(output_prefix)
    os.chdir(output_prefix)
    if os.path.exists(output_mask_fn):
        print("Use existing masks")
        masks = io.imread(output_mask_fn)
    else:
        print("Segmentating using GS and DAPI")
        masks, gs_ica = segmenting_vessels_gs_assisted(
            img, vessel_size_t=vessel_size_factor, min_dist=max_dist)
        io.imsave(output_mask_fn, masks.astype(np.uint8))

    # get CV PV classification
    cv_features = extract_features(
        masks, gs_ica, q1=gs_low, q2=gs_high, step=gs_step)
    cv_labels, pv_labels = pv_classifier(cv_features.loc[:, "I0":], masks)
    # modify CV masks to shrink their borders
    cv_masks = masks * np.isin(masks, cv_labels).copy()
    pv_masks = masks * np.isin(masks, pv_labels).copy()
    masks = shrink_cv_masks(cv_masks, pv_masks, img[:, :, 2])
    plot_pv_cv(masks, cv_labels, img, output_prefix + " ")
    # Calculate distance projections
    coords_pixel, coords_cv, coords_pv = find_pv_cv_coords(
        masks, cv_labels, pv_labels)
    orphans = find_orphans(masks, cv_labels, pv_labels)
    zone_crit = get_distance_projection(
        coords_pixel, coords_cv, coords_pv, cosine_filter=True
    )
    zone_crit[masks != 0] = -1
    zone_crit[(zone_crit > 1) | (zone_crit < 0)] = -1
    zone_crit[orphans] = -1

    # Calculate zones
    zones = create_zones(masks, zone_crit, cv_labels, pv_labels, num_zones=24)
    zone_int = plot_zone_int_probs(
        img[:, :, 0],
        img[:, :, 2],
        zones,
        dapi_cutoff="otsu",
        plot_type="probs",
        prefix=output_prefix,
    )
    zone_int.to_csv(output_prefix + ' zone int.csv')
    plot_zone_with_img(img, zones, fig_prefix=output_prefix)
