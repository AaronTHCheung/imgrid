import cv2
import argparse
import os
import itertools
from shapely import Polygon, MultiPoint, Point, distance
import math
import json
import jsonpath_ng
from tqdm import tqdm

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("json_dir", type=str, help="Directory of the LabelMe JSON annotations")
    parser.add_argument('out_dir', type=str, help="Output directory")
    parser.add_argument("width", type=int, help="Width of output pattern images")
    parser.add_argument("height", type=int, help="Height of output pattern images")
    parser.add_argument("--no_label", action='store_true', help="Do not save the label txt")
    parser.add_argument("--x_stride", type=int, help="Stride in x-direction. Default is width")
    parser.add_argument("--y_stride", type=int, help="Stride in y-direction. Default is height")

    args = parser.parse_args()

    out_absdir = os.path.abspath(args.out_dir)
    if not os.path.exists(out_absdir): os.makedirs(out_absdir)

    jsonpath_lbls = jsonpath_ng.parse('$.shapes[*].label')
    jsonpath_pts = jsonpath_ng.parse('$.shapes[*].points')
    jsonpath_shapeTypes = jsonpath_ng.parse('$.shapes[*].shape_type')
    jsonpath_imgPath = jsonpath_ng.parse('$.imagePath')

    os.chdir(args.json_dir)
    pbar = tqdm([x for x in os.listdir('.') if x.endswith('.json')])
    input_shape_count = 0
    total_rect_count = 0
    for json_filename in pbar:
        pbar.set_description(f'Current JSON: {json_filename}')
        with open(json_filename) as f:
            json_data = json.load(f)
        labels = [m.value for m in jsonpath_lbls.find(json_data)]
        ptss = [m.value for m in jsonpath_pts.find(json_data)]
        shapeTypes = [m.value for m in jsonpath_shapeTypes.find(json_data)]
        imgPath = [m.value for m in jsonpath_imgPath.find(json_data)][0]
        
        img = cv2.imread(imgPath)
        rect_count = 0
        for label, pts, shapeType in zip(labels, ptss, shapeTypes):
            if shapeType not in ['polygon', 'rectangle', 'circle']: continue
            input_shape_count += 1
            
            if shapeType == 'polygon':
                shape = Polygon(pts)  # (x, y) with origin at the upperleft
            elif shapeType == 'rectangle':
                shape = MultiPoint(pts).envelope
            elif shapeType == 'circle':
                origin = Point(pts[0])
                radius = distance(origin, Point(pts[1]))
                shape = origin.buffer(radius)

            minx, miny, maxx, maxy = shape.bounds
            minx = math.ceil(minx)
            miny = math.ceil(miny)
            maxx = math.floor(maxx)
            maxy = math.floor(maxy)

            x_stride = args.width if args.x_stride is None else args.x_stride
            y_stride = args.height if args.y_stride is None else args.y_stride
            x_steps = math.floor((maxx - minx) / x_stride)
            y_steps = math.floor((maxy - miny) / y_stride)
            for xi, yi in itertools.product(range(x_steps), range(y_steps)):
                rect = MultiPoint([ (minx + x_stride * xi,              miny + y_stride * yi),
                                    (minx + x_stride * xi + args.width, miny + y_stride * yi + args.height)]).envelope
                if shape.contains(rect): 
                    rect_count += 1
                    out_dirstem = os.path.join(
                        out_absdir,
                        f'{os.path.splitext(json_filename)[0]}_{rect_count}'
                    )
                    start_x, start_y, end_x, end_y = (int(x) for x in rect.bounds)
                    cv2.imwrite(f'{out_dirstem}.jpg',
                                img[
                                    start_y: end_y,
                                    start_x: end_x
                                ])
                    if not args.no_label:
                        with open(f'{out_dirstem}.txt', 'w') as f:
                            f.write(label)
        total_rect_count += rect_count
    print(f'{total_rect_count} texture images created from {input_shape_count} shapes')

if __name__ == '__main__':
    main()