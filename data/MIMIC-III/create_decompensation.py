import os
import argparse
import numpy as np
import pandas as pd
import random
random.seed(49297)
from tqdm import tqdm


def process_partition(args, partition, sample_rate=1.0, shortest_length=4.0,
                      eps=1e-6, future_time_interval=24.0):

    output_dir = os.path.join(args.output_path, partition)
    if not os.path.exists(output_dir):
        os.mkdir(output_dir)

    xty_triples = []
    patients = list(filter(str.isdigit, os.listdir(os.path.join(args.root_path, partition))))
    for patient in tqdm(patients, desc='Iterating over patients in {}'.format(partition)):
        patient_folder = os.path.join(args.root_path, partition, patient)
        patient_ts_files = list(filter(lambda x: x.find("timeseries") != -1, os.listdir(patient_folder)))
        stays_df = pd.read_csv(os.path.join(patient_folder, "stays.csv"))

        for ts_filename in patient_ts_files:
            with open(os.path.join(patient_folder, ts_filename)) as tsfile:
                lb_filename = ts_filename.replace("_timeseries", "")
                label_df = pd.read_csv(os.path.join(patient_folder, lb_filename))

                # empty label file
                if label_df.shape[0] == 0:
                    continue

                mortality = int(label_df.iloc[0]["Mortality"])

                los = 24.0 * label_df.iloc[0]['Length of Stay']  # in hours
                if pd.isnull(los):
                    print("(length of stay is missing)", patient, ts_filename)
                    continue

                stay = stays_df[stays_df.ICUSTAY_ID == label_df.iloc[0]['Icustay']]
                deathtime = pd.to_datetime(stay['DEATHTIME'].iloc[0]) # 记录死亡时间
                intime = pd.to_datetime(stay['INTIME'].iloc[0]) # 记录入院时间
                if pd.isnull(deathtime):
                    lived_time = 1e18 # 如果为空，则没死，用个超级大的数
                else:
                    # conversion to pydatetime is needed to avoid overflow issues when subtracting
                    lived_time = (deathtime.to_pydatetime() - intime.to_pydatetime()).total_seconds() / 3600.0 # 不然记录下还有多久死。就是live time

                ts_lines = tsfile.readlines()
                header = ts_lines[0]
                ts_lines = ts_lines[1:]
                event_times = [float(line.split(',')[0]) for line in ts_lines]

                ts_lines = [line for (line, t) in zip(ts_lines, event_times)
                            if -eps < t < los + eps]
                event_times = [t for t in event_times
                               if -eps < t < los + eps]

                # no measurements in ICU
                if len(ts_lines) == 0:
                    print("(no events in ICU) ", patient, ts_filename)
                    continue

                # sample_times = np.arange(0.0, min(los, lived_time) + eps, sample_rate)

                # sample_times = list(filter(lambda x: x > shortest_length, sample_times))

                # # At least one measurement
                # sample_times = list(filter(lambda x: x > event_times[0], sample_times))
                
                t = min(24, int(los), int(lived_time)) # 这里看下最小值。
                if len(event_times) < 2 or event_times[1] > t: # 只有一次event，并且第二次时间就比live时间长，就过滤掉这个数据。
                    print("(no enough data) ", patient, ts_filename)
                    continue

                output_ts_filename = patient + "_" + ts_filename
                with open(os.path.join(output_dir, output_ts_filename), "w") as outfile:
                    outfile.write(header)
                    for line in ts_lines:
                        outfile.write(line)
                        
                if mortality == 0: # 应该是记录没死。
                    cur_mortality = 0 
                else:
                    cur_mortality = int(lived_time - t < future_time_interval)# 没死就计算下，如果lived_time - t间隔不足24h，就算死；反之就算0。
                xty_triples.append((output_ts_filename, t, cur_mortality))

    print("Number of created samples:", len(xty_triples))
    if partition == "train":
        random.shuffle(xty_triples)
    if partition == "test":
        xty_triples = sorted(xty_triples)

    with open(os.path.join(output_dir, "listfile.csv"), "w") as listfile:
        listfile.write('stay,period_length,y_true\n')
        for (x, t, y) in xty_triples:
            listfile.write('{},{:.6f},{:d}\n'.format(x, t, y))


def main():
    parser = argparse.ArgumentParser(description="Create data for decompensation prediction task.")
    parser.add_argument('root_path', type=str, help="Path to root folder containing train and test sets.")
    parser.add_argument('output_path', type=str, help="Directory where the created data should be stored.")
    args, _ = parser.parse_known_args()

    if not os.path.exists(args.output_path):
        os.makedirs(args.output_path)

    process_partition(args, "test")
    process_partition(args, "train")


if __name__ == '__main__':
    main()
