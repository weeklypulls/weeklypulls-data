# -*- coding: utf-8 -*-
# Generated manually on 2025-07-31
from __future__ import unicode_literals

from django.db import migrations, models
from collections import defaultdict


def convert_series_ids(apps, schema_editor):
    """
    Convert Marvel series IDs to ComicVine series IDs and merge records where necessary.
    """
    Pull = apps.get_model('pulls', 'Pull')
    MUPull = apps.get_model('pulls', 'MUPull')
    MUPullAlert = apps.get_model('pulls', 'MUPullAlert')
    
    # Report initial counts
    print(f"Starting migration with {Pull.objects.count()} Pulls, {MUPull.objects.count()} MUPulls, {MUPullAlert.objects.count()} MUPullAlerts")
    
    # Marvel ID => ComicVine ID mapping
    # TODO: Replace this placeholder mapping with your generated list
    marvel_to_comicvine_mapping = {
        19427: 97041,
        19679: 87182,
        20432: 87154,
        20457: 150556,
        20465: 85290,
        20488: 89613,
        20499: 86251,
        20502: 87449,
        20505: 85311,
        20508: 87820,
        20511: 85312,
        20527: 86113,
        20613: 85750,
        20614: 86408,
        20615: 84173,
        20617: 87624,
        20620: 85601,
        20621: 119941,
        20682: 85930,
        20711: 85274,
        20720: 85938,
        20780: 116561,
        20818: 94811,
        20839: 86245,
        20845: 86780,
        20879: 90118,
        20884: 90125,
        21098: 90698,
        21122: 88214,
        21490: 89627,
        21608: 3006,
        21942: 87793,
        22439: 100830,
        22465: 109533,
        22466: 114948,
        22467: 109533,
        22493: 100819,
        22530: 98512,
        22533: 96661,
        22545: 157267,
        22547: 95402,
        22551: 97062,
        22552: 141587,
        22560: 95211,
        22561: 9541,
        22562: 94801,
        22580: 146723,
        22596: 95016,
        22645: 85178,
        22647: 10989,
        22648: 85778,
        22649: 95431,
        22651: 101410,
        22652: 97073,
        22653: 95750,
        22656: 119325,
        22657: 110770,
        22658: 114425,
        22718: 97430,
        22928: 85110,
        22929: 95843,
        22993: 100082,
        23012: 100709,
        23016: 100603,
        23018: 125905,
        23020: 105552,
        23021: 100966,
        23026: 100590,
        23029: 102287,
        23040: 101478,
        23044: 101195,
        23045: 101484,
        23046: 101788,
        23047: 101411,
        23048: 101638,
        23072: 103811,
        23074: 102109,
        23079: 102133,
        23096: 101937,
        23101: 102272,
        23103: 101954,
        23104: 102273,
        23121: 101166,
        23125: 102455,
        23126: 106295,
        23251: 102777,
        23262: 102882,
        23277: 112027,
        23278: 103816,
        23279: 103514,
        23280: 103386,
        23281: 86408,
        23282: 103605,
        23447: 104089,
        23451: 104475,
        23456: 104625,
        23461: 104320,
        23468: 104088,
        23602: 104999,
        23603: 104938,
        23635: 105325,
        23675: 82104,
        23677: 106134,
        23679: 18919,
        23680: 105965,
        23681: 4810,
        23769: 106662,
        23771: 107157,
        23772: 107368,
        23774: 107169,
        23868: 107513,
        23899: 119596,
        23906: 107934,
        23907: 108101,
        23911: 108127,
        23974: 142134,
        23991: 108528,
        24016: 108809,
        24050: 109103,
        24096: 109444,
        24137: 10904,
        24144: 109637,
        24155: 109764,
        24199: 114714,
        24229: 119674,
        24235: 110516,
        24237: 110933,
        24255: 78715,
        24278: 111425,
        24279: 117067,
        24290: 111397,
        24294: 102965,
        24296: 106673,
        24300: 108818,
        24302: 111044,
        24305: 111839,
        24308: 123862,
        24309: 111704,
        24312: 111584,
        24315: 115739,
        24316: 115740,
        24317: 111043,
        24329: 148668,
        24338: 111142,
        24339: 110922,
        24340: 112453,
        24347: 110925,
        24369: 113074,
        24374: 110945,
        24396: 112161,
        24554: 112685,
        24669: 111413,
        24738: 18639,
        24781: 56425,
        24906: 111676,
        24909: 111677,
        25133: 111583,
        25139: 84173,
        25141: 113496,
        25147: 84173,
        25200: 112458,
        25256: 111688,
        25314: 20454,
        25494: 3488,
        25575: 112977,
        25582: 113726,
        25602: 125787,
        25796: 114425,
        25804: 117975,
        25943: 115418,
        25951: 113264,
        25987: 115566,
        25991: 118154,
        25996: 113217,
        25998: 112806,
        25999: 115897,
        26000: 113250,
        26001: 154800,
        26003: 114734,
        26004: 114089,
        26005: 116160,
        26006: 112791,
        26007: 116483,
        26008: 2351,
        26009: 74330,
        26032: 101937,
        26038: 115285,
        26043: 113258,
        26044: 48014,
        26045: 113494,
        26080: 116561,
        26087: 114912,
        26098: 112797,
        26156: 113865,
        26157: 114715,
        26158: 113884,
        26159: 115395,
        26160: 113710,
        26161: 114416,
        26172: 115575,
        26176: 114916,
        26177: 114733,
        26256: 115752,
        26257: 116079,
        26259: 114867,
        26267: 78715,
        26270: 33249,
        26286: 113703,
        26328: 116812,
        26330: 116954,
        26331: 117041,
        26332: 117190,
        26333: 117339,
        26334: 117431,
        26335: 121222,
        26338: 120309,
        26340: 120407,
        26369: 117231,
        26409: 115259,
        26410: 117341,
        26475: 115237,
        26476: 117581,
        26477: 115877,
        26478: 116068,
        26479: 115881,
        26481: 115743,
        26483: 115754,
        26484: 115905,
        26486: 114426,
        26487: 114427,
        26488: 114919,
        26489: 37503,
        26491: 114741,
        26492: 114100,
        26493: 115772,
        26590: 7167,
        26592: 29412,
        26646: 116708,
        26673: 116365,
        26676: 137565,
        26679: 116368,
        26683: 120130,
        26835: 115775,
        26892: 118135,
        26898: 116253,
        26899: 116502,
        26911: 117766,
        26914: 120141,
        26980: 48014,
        26981: 117610,
        27019: 137613,
        27020: 18577,
        27128: 119141,
        27130: 117444,
        27131: 117975,
        27133: 117593,
        27137: 119315,
        27138: 118673,
        27139: 119170,
        27184: 118139,
        27244: 121907,
        27272: 120532,
        27288: 120643,
        27314: 119520,
        27319: 122500,
        27320: 120964,
        27382: 118402,
        27419: 119169,
        27421: 122215,
        27505: 121118,
        27547: 122488,
        27552: 122814,
        27554: 4595,
        27555: 122218,
        27557: 122666,
        27564: 125859,
        27567: 117893,
        27601: 22871,
        27606: 121077,
        27619: 121119,
        27620: 123766,
        27622: 120816,
        27624: 18400,
        27631: 122065,
        27632: 121731,
        27633: 120945,
        27634: 120946,
        27635: 120627,
        27637: 121056,
        27720: 120811,
        27730: 121221,
        27739: 11023,
        27824: 120545,
        27838: 85750,
        27849: 123765,
        27884: 124822,
        27932: 121896,
        27980: 122984,
        27981: 151000,
        27982: 123264,
        27983: 123408,
        27984: 123407,
        27985: 123263,
        27986: 123709,
        28031: 123862,
        28037: 137254,
        28038: 151096,
        28039: 49036,
        28041: 123712,
        28042: 116702,
        28046: 130567,
        28048: 150801,
        28051: 125121,
        28053: 129097,
        28060: 122214,
        28064: 121744,
        28109: 18445,
        28114: 122988,
        28148: 128152,
        28163: 123768,
        28177: 125477,
        28205: 123276,
        28289: 122986,
        28290: 122487,
        28397: 4421,
        29032: 124815,
        29034: 29412,
        29045: 125811,
        29274: 128447,
        29275: 128103,
        29276: 130186,
        29281: 128616,
        29326: 126014,
        29329: 33405,
        29334: 125302,
        29357: 123122,
        29358: 18412,
        29359: 34138,
        29384: 132229,
        29389: 86251,
        29493: 134219,
        29606: 129251,
        29643: 2569,
        29648: 124988,
        29688: 130569,
        29689: 131525,
        29690: 132228,
        29700: 116493,
        29713: 132377,
        29714: 136143,
        30126: 126017,
        30148: 160522,
        30175: 126015,
        30518: 128881,
        30519: 128103,
        30520: 129094,
        30521: 129095,
        30527: 128880,
        30529: 129246,
        30533: 129649,
        30536: 111425,
        30844: 2351,
        31076: 116483,
        31082: 2905,
        31083: 141233,
        31086: 78715,
        31090: 4595,
        31102: 2350,
        31103: 138346,
        31105: 28094,
        31115: 138532,
        31129: 150868,
        31209: 130394,
        31223: 130187,
        31322: 119520,
        31324: 137402,
        31330: 136937,
        31374: 140213,
        31375: 149617,
        31392: 135583,
        31549: 134389,
        31559: 138155,
        31717: 141329,
        31892: 134220,
        31893: 136935,
        31896: 143940,
        31898: 139125,
        31902: 136143,
        31905: 149621,
        32001: 143994,
        32071: 137698,
        32125: 140533,
        32136: 136022,
        32137: 137255,
        32281: 138343,
        32384: 137254,
        32866: 152139,
        32868: 138527,
        32871: 139125,
        32873: 140282,
        32874: 140283,
        32875: 140357,
        32876: 141326,
        32925: 140355,
        32952: 140354,
        32953: 140220,
        32954: 150684,
        32956: 141459,
        32958: 86251,
        32961: 142143,
        32962: 147358,
        33271: 2766,
        33281: 157407,
        33287: 139124,
        33917: 141328,
        33948: 141457,
        33949: 152139,
        33959: 143115,
        33961: 147311,
        33968: 150088,
        34025: 158866,
        34026: 141176,
        34029: 149050,
        34035: 145912,
        34152: 141844,
        34153: 141785,
        34154: 146134,
        34155: 146135,
        34156: 141458,
        34157: 141525,
        34158: 141917,
        34274: 141784,
        34359: 144437,
        34441: 128840,
        34446: 143032,
        34459: 148828,
        34471: 143856,
        34558: 149645,
        34624: 144027,
        34651: 152587,
        34717: 146873,
        35342: 130207,
        35453: 145299,
        35454: 145486,
        35455: 144577,
        35456: 144026,
        35457: 145362,
        35458: 145363,
        35519: 146113,
        35521: 146987,
        35566: 150051,
        35626: 144576,
        35628: 144438,
        35717: 153860,
        36206: 150051,
        36207: 146986,
        36208: 146875,
        36247: 145487,
        36268: 145974,
        36857: 143032,
        37239: 78715,
        37674: 153238,
        37695: 48014,
        37824: 160344,
        37835: 154675,
        38458: 161847,
        38699: 154414,
        38806: 156647,
        38809: 155969,
        38817: 157127,
        38831: 10748,
        38836: 154069,
        38860: 157398,
        38865: 158414,
        39200: 3519,
        39284: 157504,
        39362: 123862,
        39482: 154417,
    }
    
    if not marvel_to_comicvine_mapping:
        print("Warning: No mapping provided. Skipping migration.")
        return
    
    # Convert and merge Pull records
    convert_and_merge_pulls(Pull, marvel_to_comicvine_mapping)
    
    # Convert and merge MUPull records
    convert_and_merge_mupulls(MUPull, marvel_to_comicvine_mapping)
    
    # Convert MUPullAlert records (no merging needed as they don't have unique constraints)
    convert_mupull_alerts(MUPullAlert, marvel_to_comicvine_mapping)
    
    # Report final counts
    print(f"Migration completed. Final counts: {Pull.objects.count()} Pulls, {MUPull.objects.count()} MUPulls, {MUPullAlert.objects.count()} MUPullAlerts")


def convert_and_merge_pulls(Pull, mapping):
    """Convert Pull records and merge duplicates."""
    print("Converting Pull records...")
    
    # Group pulls by pull_list and target ComicVine series_id
    merge_groups = defaultdict(list)
    
    for pull in Pull.objects.all():
        if pull.series_id in mapping:
            comicvine_id = mapping[pull.series_id]
            key = (pull.pull_list_id, comicvine_id)
            merge_groups[key].append(pull)
    
    for (pull_list_id, comicvine_id), pulls in merge_groups.items():
        if len(pulls) == 1:
            # Simple case: just update the series_id
            pull = pulls[0]
            pull.series_id = comicvine_id
            pull.save()
            print(f"Updated Pull id={pull.id} series_id to {comicvine_id}")
        else:
            # Merge case: combine read and skipped arrays, keep the first record
            primary_pull = pulls[0]
            primary_pull.series_id = comicvine_id
            
            # Merge read and skipped arrays from all pulls
            all_read = set(primary_pull.read or [])
            all_skipped = set(primary_pull.skipped or [])
            
            for pull in pulls[1:]:
                if pull.read:
                    all_read.update(pull.read)
                if pull.skipped:
                    all_skipped.update(pull.skipped)
                
                print(f"Deleting duplicate Pull id={pull.id} (merged into {primary_pull.id})")
                pull.delete()
            
            # Update primary pull with merged data
            primary_pull.read = list(all_read)
            primary_pull.skipped = list(all_skipped)
            primary_pull.save()
            
            print(f"Merged {len(pulls)} Pull records into id={primary_pull.id} with series_id={comicvine_id}")


def convert_and_merge_mupulls(MUPull, mapping):
    """Convert MUPull records and merge duplicates."""
    print("Converting MUPull records...")
    
    # Group MUPulls by pull_list and target ComicVine series_id
    merge_groups = defaultdict(list)
    
    for mupull in MUPull.objects.all():
        if mupull.series_id in mapping:
            comicvine_id = mapping[mupull.series_id]
            key = (mupull.pull_list_id, comicvine_id)
            merge_groups[key].append(mupull)
    
    for (pull_list_id, comicvine_id), mupulls in merge_groups.items():
        if len(mupulls) == 1:
            # Simple case: just update the series_id
            mupull = mupulls[0]
            mupull.series_id = comicvine_id
            mupull.save()
            print(f"Updated MUPull id={mupull.id} series_id to {comicvine_id}")
        else:
            # Merge case: keep the earliest created record, delete the rest
            primary_mupull = min(mupulls, key=lambda x: x.created_at)
            primary_mupull.series_id = comicvine_id
            primary_mupull.save()
            
            for mupull in mupulls:
                if mupull.id != primary_mupull.id:
                    print(f"Deleting duplicate MUPull id={mupull.id} (merged into {primary_mupull.id})")
                    mupull.delete()
            
            print(f"Merged {len(mupulls)} MUPull records into id={primary_mupull.id} with series_id={comicvine_id}")


def convert_mupull_alerts(MUPullAlert, mapping):
    """Convert MUPullAlert records (no merging needed)."""
    print("Converting MUPullAlert records...")
    
    for alert in MUPullAlert.objects.all():
        if alert.series_id in mapping:
            old_id = alert.series_id
            alert.series_id = mapping[old_id]
            alert.save()
            print(f"Updated MUPullAlert id={alert.id} series_id from {old_id} to {alert.series_id}")


def reverse_convert_series_ids(apps, schema_editor):
    """
    Reverse migration - this is complex because we lose information during merging.
    This is a best-effort reverse that won't perfectly restore the original state.
    """
    print("Warning: Reverse migration cannot perfectly restore merged records.")
    print("Original Marvel series IDs and merged records are lost.")
    
    # In a real scenario, you might want to prevent reverse migration
    # or implement a more sophisticated approach with backup tables
    raise NotImplementedError(
        "Reverse migration is not supported because record merging is irreversible. "
        "Please restore from a database backup if you need to revert this migration."
    )


class Migration(migrations.Migration):

    dependencies = [
        ('pulls', '0011_mupull_mupullalert'),
    ]

    operations = [
        migrations.RunPython(
            convert_series_ids,
            reverse_convert_series_ids,
        ),
    ]
