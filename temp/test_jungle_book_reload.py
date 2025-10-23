"""Test script to verify multi-entry gap info works for Jungle Book songs"""
import sys
import os
import asyncio
import json

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from services.song_service import SongService
from services.gap_info_service import GapInfoService

async def test_jungle_book():
    folder = r"Z:\UltraStarDeluxe\Songs\TV\The Jungle Book - I Wanna Be Like You"
    louis_txt = os.path.join(folder, "The Jungle Book - I Wanna Be Like You (Louis).txt")
    baloo_txt = os.path.join(folder, "The Jungle Book - I Wanna Be Like You (Baloo).txt")
    info_file = os.path.join(folder, "usdxfixgap.info")
    
    print("=" * 80)
    print("BEFORE RELOAD")
    print("=" * 80)
    with open(info_file, 'r', encoding='utf-8') as f:
        data = json.load(f)
        print(f"Format version: {data.get('version', 1)}")
        print(f"Top-level keys: {list(data.keys())[:10]}")
        if 'entries' in data:
            print(f"Entries: {list(data['entries'].keys())}")
        print()
    
    # Load both songs
    song_service = SongService()
    
    print("=" * 80)
    print("LOADING LOUIS...")
    print("=" * 80)
    louis = await song_service.load_song(louis_txt, force_reload=True)
    print(f"Title: {louis.title}")
    print(f"Audio: {louis.audio}")
    print(f"Audio file exists: {os.path.exists(louis.audio_file)}")
    print(f"Gap: {louis.gap}")
    print(f"Gap info status: {louis.gap_info.status}")
    print(f"Gap info txt_basename: {louis.gap_info.txt_basename}")
    print(f"Gap info detected_gap: {louis.gap_info.detected_gap}")
    print()
    
    print("=" * 80)
    print("LOADING BALOO...")
    print("=" * 80)
    baloo = await song_service.load_song(baloo_txt, force_reload=True)
    print(f"Title: {baloo.title}")
    print(f"Audio: {baloo.audio}")
    print(f"Audio file exists: {os.path.exists(baloo.audio_file)}")
    print(f"Gap: {baloo.gap}")
    print(f"Gap info status: {baloo.gap_info.status}")
    print(f"Gap info txt_basename: {baloo.gap_info.txt_basename}")
    print(f"Gap info detected_gap: {baloo.gap_info.detected_gap}")
    print()
    
    # Now let's simulate what happens when gap detection finishes for Louis
    print("=" * 80)
    print("SIMULATING GAP DETECTION SAVE FOR LOUIS...")
    print("=" * 80)
    louis.gap_info.status = "UPDATED"
    louis.gap_info.detected_gap = 1996  # First silence period from the data
    louis.gap_info.updated_gap = 1938   # The GAP value from txt file
    await GapInfoService.save(louis.gap_info)
    print("Saved!")
    print()
    
    print("=" * 80)
    print("AFTER SAVE - FILE CONTENTS")
    print("=" * 80)
    with open(info_file, 'r', encoding='utf-8') as f:
        data = json.load(f)
        print(f"Format version: {data.get('version', 'N/A')}")
        if 'entries' in data:
            print(f"Entries: {list(data['entries'].keys())}")
            for key, value in data['entries'].items():
                print(f"\n{key}:")
                print(f"  status: {value.get('status')}")
                print(f"  detected_gap: {value.get('detected_gap')}")
                print(f"  updated_gap: {value.get('updated_gap')}")
        else:
            print("STILL SINGLE ENTRY FORMAT!")
            print(f"Keys: {list(data.keys())[:10]}")
    print()
    
    # Reload both songs to see if they get correct data
    print("=" * 80)
    print("RELOADING BOTH SONGS...")
    print("=" * 80)
    louis2 = await song_service.load_song(louis_txt, force_reload=True)
    baloo2 = await song_service.load_song(baloo_txt, force_reload=True)
    print(f"Louis gap_info status: {louis2.gap_info.status}, detected_gap: {louis2.gap_info.detected_gap}")
    print(f"Baloo gap_info status: {baloo2.gap_info.status}, detected_gap: {baloo2.gap_info.detected_gap}")
    print()
    
    print("=" * 80)
    print("TEST COMPLETE")
    print("=" * 80)

if __name__ == '__main__':
    asyncio.run(test_jungle_book())
