import cv2
import argparse
import os

def process_video(input_file, crop_side, rotate, save_frames=False):
    # Open video file
    cap = cv2.VideoCapture(input_file)

    # Get video properties
    fps = int(cap.get(cv2.CAP_PROP_FPS))
    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    number_of_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))

    # Determine output filename
    base_name, ext = os.path.splitext(input_file)
    output_file = f"{base_name}{'_rotated' if rotate else ''}{'_' + crop_side if crop_side == 'left' or crop_side == 'right' else ''}.mp4"


    if save_frames:
        parent_dir = os.path.dirname(input_file)
        output_dir = os.path.join(parent_dir, 'frames')
        file_name = os.path.basename(output_file)
        print(f'Saving frames to {output_dir}')
        if not os.path.exists(output_dir):
            os.makedirs(output_dir)

    # Define video writer
    fourcc = cv2.VideoWriter_fourcc(*'mp4v')
    if crop_side == "left" or crop_side == "right":
        out = cv2.VideoWriter(output_file, fourcc, fps, (width // 2, height))
    else:
        out = cv2.VideoWriter(output_file, fourcc, fps, (width, height))
    i=0
    while cap.isOpened():
        ret, frame = cap.read()
        if not ret:
            break  # End of video

        # Rotate if specified
        if rotate:
            frame = cv2.rotate(frame, cv2.ROTATE_180)

        # Crop left or right half
        if crop_side == "left":
            frame = frame[:, :width // 2]  # Left half
        elif crop_side == "right":
            frame = frame[:, width // 2:]  # Right half

        if save_frames:
            frame_name = os.path.join(output_dir, f"{i}_" + file_name[:-4]+".jpg")
            cv2.imwrite(frame_name, frame)
        print(f'Processing frame {i}/{number_of_frames}', end='\r', flush=True)
        i+=1
        # Write processed frame
        out.write(frame)

    # Release resources
    cap.release()
    out.release()
    cv2.destroyAllWindows()

    print(f"Processing complete. Saved as: {output_file}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Process video: rotate & crop half")
    parser.add_argument("video", help="Input video file")
    parser.add_argument("-l", "--left", action="store_true", help="Crop left half")
    parser.add_argument("-r", "--right", action="store_true", help="Crop right half")
    parser.add_argument("-rotate", action="store_true", help="Rotate 180 degrees")
    parser.add_argument("-s", "--save-frames", action="store_true", help="Save frames")

    args = parser.parse_args()

    # Determine cropping side
    crop_side = "left" if args.left else "right" if args.right else None

    if crop_side is None and not args.rotate and not args.save_frames:
        print("No action specified. Use --left, --right, --rotate or --save-frames")
        exit(1)

    # Process the video
    process_video(args.video, crop_side, args.rotate, args.save_frames)
