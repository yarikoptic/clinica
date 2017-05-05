def compute_fmri_path( source_dir, clinical_dir, dest_dir, subjs_list):
    '''
    Compute the paths to fmri images.

    The fmri images to convert into BIDS are chosen in the following way:
        - Extract the list of subjects from MAYOADIRL_MRI_FMRI_09_15_16.csv
        - Select the only the scans that came from PHILIPS machine (field Scanner from IDA_MR_Metadata_Listing.csv)
        - Discard all the subjects with column  series_quality = 4  (4 means that the scan is not usable) in MAYOADIRL_MRI_IMAGEQC_12_08_15.csv

    In case of multiple scans for the same session, same date the one to convert is chosen with the following criteria:
        - Check if in the file MAYOADIRL_MRI_IMAGEQC_12_08_15.csv there is a single scan with the field series_selected == 1
        - If yes choose the one with series_selected == 1
        - If no choose the scan with the best quality


    :param source_dir: path to the ADNI image folder
    :param clinical_dir: path to the directory with all the clinical data od ADNI
    :param dest_dir: path to the output_folder
    :param subjs_list: subjects list
    :return: pandas Dataframe containing the path for each fmri
    '''
    import os
    from os import path
    from os import walk
    import pandas as pd
    import logging

    fmri_col = ['Subject_ID', 'VISCODE', 'Visit', 'IMAGEUID', 'Sequence', 'Scan Date', 'LONIUID', 'Scanner',
                'MagStregth', 'Path']

    fmri_df = pd.DataFrame(columns=fmri_col)

    # Load the requested clinical data
    mayo_mri_fmri_path = path.join(clinical_dir, 'MAYOADIRL_MRI_FMRI_09_15_16.csv')
    mayo_mri_imageqc_path = path.join(clinical_dir, 'MAYOADIRL_MRI_IMAGEQC_12_08_15.csv')
    ida_mr_metadata_path = path.join(clinical_dir, 'IDA_MR_Metadata_Listing.csv')

    mayo_mri_fmri = pd.io.parsers.read_csv(mayo_mri_fmri_path, sep=',')
    ida_mr_metadata = pd.io.parsers.read_csv(ida_mr_metadata_path, sep=',')
    mayo_mri_imageqc = pd.io.parsers.read_csv(mayo_mri_imageqc_path, sep=',')

    for subj in subjs_list:
        print subj
        fmri_subjs_info = mayo_mri_fmri[(mayo_mri_fmri.RID == int(subj[-4:]))]
        # Extract visits available
        visits_list = fmri_subjs_info['VISCODE2'].tolist()
        # Removing duplicates
        visits_list = list(set(visits_list))

        if len(visits_list) != 0:
            for viscode in visits_list:
                scan_date = ''
                sequence = ''
                loni_uid = ''
                visit = ''
                mag_strenght = ''
                image_path = ''

                fmri_subj = fmri_subjs_info[fmri_subjs_info['VISCODE2'] == viscode]

                if not fmri_subj.empty:

                    # If there are multiple scans for the same session same subject, check what is the one selected for the usage (field 'series_selected') or
                    # choose the one with the best quality
                    if len(fmri_subj) > 1:
                        fmri_imageuid = fmri_subj['IMAGEUID'].tolist()
                        loni_uid_list = ['I' + str(imageuid) for imageuid in fmri_imageuid]
                        images_qc = mayo_mri_imageqc[mayo_mri_imageqc.loni_image.isin(loni_uid_list)]
                        series_selected_values = images_qc['series_selected'].tolist()
                        sum_series_selected = sum(series_selected_values)
                        if sum_series_selected == 1:
                            imageuid_to_select = images_qc[images_qc['series_selected'] > 0]['loni_image'].iloc[
                                0].replace('I', '')
                        else:
                            imageuid_to_select = self.select_image_qc(fmri_imageuid, images_qc)

                        fmri_subj = fmri_subj[fmri_subj['IMAGEUID'] == int(imageuid_to_select)].iloc[0]
                    else:
                        fmri_subj = fmri_subj.iloc[0]

                    fmri_imageuid = fmri_subj['IMAGEUID']

                    # Discard scans made with non Philips scanner and with a bad quality
                    fmri_metadata = ida_mr_metadata[ida_mr_metadata['IMAGEUID'] == fmri_imageuid]

                    if not fmri_metadata.empty:
                        fmri_metadata = fmri_metadata.iloc[0]

                        if not 'Philips' in fmri_metadata['Scanner']:
                            print 'No Philips scanner for ', subj, 'visit', viscode, '. Skipped.'
                            continue

                        elif 4 in mayo_mri_imageqc[mayo_mri_imageqc['loni_image'] == 'I' + str(fmri_imageuid)][
                            'series_quality'].values:
                            print 'Bad scan quality for ', subj, 'visit', viscode, '. Skipped.'
                            continue

                        scan_date = fmri_subj.SCANDATE
                        sequence = self.replace_sequence_chars(fmri_subj.SERDESC)
                        scanner = fmri_metadata['Scanner']
                        loni_uid = fmri_metadata['LONIUID']
                        visit = fmri_metadata['Visit']
                        mag_strenght = fmri_metadata['MagStrength']

                        # Calculate the path
                        seq_path = path.join(source_dir, str(subj), sequence)
                        for (dirpath, dirnames, filenames) in walk(seq_path):
                            found = False
                            for d in dirnames:
                                if d == 'S' + str(loni_uid):
                                    image_path = path.join(dirpath, d)
                                    # Check if the path exists
                                    if not os.path.isdir(image_path):
                                        print 'Path not existing for subject:', subj, 'visit:', visit
                                    found = True
                                    break
                            if found:
                                break

                        # The session scmri correspond to the baseline
                        if viscode == 'scmri':
                            viscode = 'bl'
                    else:
                        print 'Missing visit, sequence, scan date and loniuid for ', subj, 'visit', visit
                        continue

                    row_to_append = pd.DataFrame(
                        [[subj, str(viscode), visit, str(fmri_imageuid), sequence, scan_date, str(loni_uid),
                          scanner, mag_strenght, image_path]], columns=fmri_col)

                    fmri_df = fmri_df.append(row_to_append, ignore_index=True)
                else:
                    logging.info('Missing fMRI for ', subj, 'visit', visit)

    fmri_df.to_csv(path.join(dest_dir, 'conversion_info', 'fmri_paths.tsv'), sep='\t', index=False)
    return fmri_df

def convert_fmri(dest_dir, subjs_list, fmri_paths, mod_to_add=False, mod_to_update=False):

    '''
    Convert the fmri extracted from the fmri_paths to BIDS

    :param input_dir: path to the input directory
    :param out_dir: path to the BIDS directory
    :param subjs_list: subjects list
    :param fmri_paths: paths to all fmri images
    :param mod_to_add: if True add the fmri only where is missing
    :param mod_to_update: if True overwrite (or create if is missing) all the existing fmri
    :return: None
    '''

    import clinica.bids.bids_utils as bids
    from os import path
    import os
    import shutil
    from glob import glob

    for i in range(0, len(subjs_list)):
        print 'Converting fmri for subject', subjs_list[i]
        sess_list = fmri_paths[(fmri_paths['Subject_ID'] == subjs_list[i])]['VISCODE'].values
        alpha_id = bids.remove_space_and_symbols(subjs_list[i])
        bids_id = 'sub-ADNI' + alpha_id

        # For each session available, create the folder if doesn't exist and convert the files
        for ses in sess_list:
            bids_ses_id = 'ses-' + ses
            bids_file_name = bids_id + '_ses-' + ses
            ses_path = path.join(dest_dir, bids_id, bids_ses_id)

            # If the fmri already exist

            existing_fmri = glob(path.join(ses_path, 'func', '*_bold*'))
            print existing_fmri
            if mod_to_add:
                if len(existing_fmri) > 0:
                    print 'Fmri already existing. Skipped.'
                    continue

            if mod_to_update and len(existing_fmri) > 0:
                print 'Removing the old fmri folder...'
                os.remove(existing_fmri[0])

            if not os.path.exists(ses_path):
                os.mkdir(ses_path)

            fmri_info = fmri_paths[(fmri_paths['Subject_ID'] == subjs_list[i]) & (fmri_paths['VISCODE'] == ses)]

            if not fmri_info['Path'].empty:
                if type(fmri_info['Path'].values[0]) != float:
                    if not os.path.exists(path.join(ses_path, 'func')):
                        os.mkdir(path.join(ses_path, 'func'))
                    fmri_path = fmri_info['Path'].values[0]
                    dcm_to_convert = check_two_dcm_folder(fmri_path, dest_dir,
                                                                fmri_info['IMAGEUID'].values[0])
                    bids.convert_fmri(dcm_to_convert, path.join(ses_path, 'func'), bids_file_name)

                    # Delete the temporary folder used for copying fmri with 2 subjects inside the DICOM folder
                    if os.path.exists(path.join(dest_dir, 'tmp_dcm_folder')):
                        shutil.rmtree(path.join(dest_dir, 'tmp_dcm_folder'))

def check_two_dcm_folder(dicom_path, bids_folder, image_uid):
    '''
    Check if a folder contains more than one DICOM and if yes, copy the DICOM related to image id passed as parameter into
    a temporary folder called tmp_dicom_folder.

    :param dicom_path: path to the DICOM folder
    :param bids_folder: path to the BIDS folder where the dataset will be stored
    :param image_uid: image id of the fmri
    :return: the path to the original DICOM folder or the path to a temporary folder called tmp_dicom_folder where only
     the DICOM to convert is copied

    '''
    from glob import glob
    from os import path
    from shutil import copy
    import shutil
    import os

    temp_folder_name = 'tmp_dcm_folder'
    dest_path = path.join(bids_folder, temp_folder_name)

    # Check if there is more than one xml file inside the folder
    xml_list = glob(path.join(dicom_path,'*.xml*'))

    if len(xml_list) > 1:
        # Remove the precedent tmp_dcm_folder if is existing
        if os.path.exists(dest_path):
            shutil.rmtree(dest_path)
        os.mkdir(dest_path)
        dmc_to_conv = glob(path.join(dicom_path,'*'+str(image_uid)+'.dcm*'))
        for d in dmc_to_conv:
            copy(d, dest_path)
        return dest_path
    else:
        return dicom_path