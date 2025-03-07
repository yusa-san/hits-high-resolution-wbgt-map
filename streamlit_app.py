import os
import streamlit as st
import pandas as pd
import geopandas as gpd
import requests
import rasterio
from rasterio.io import MemoryFile
import matplotlib.pyplot as plt
import folium
from streamlit_folium import st_folium

def file_selection_screen():
    st.header("ファイル選択")
    selected_files = []

    # 1. Inputフォルダからの選択
    st.subheader("【1】Inputフォルダからファイル選択")
    input_folder = "input"
    if os.path.isdir(input_folder):
        folder_files = os.listdir(input_folder)
        supported_exts = ['.csv', '.geojson', '.tiff', '.tif']
        folder_files = [f for f in folder_files if any(f.lower().endswith(ext) for ext in supported_exts)]
        folder_selected = st.multiselect("Inputフォルダ内のファイル", folder_files)
        for f in folder_selected:
            file_info = {"source": "folder", "name": f, "path": os.path.join(input_folder, f)}
            ext = os.path.splitext(f)[1].lower()
            if ext == ".csv":
                try:
                    df = pd.read_csv(file_info["path"])
                    st.write(f"**{f} プレビュー:**")
                    st.dataframe(df.head())
                except Exception as e:
                    st.error(f"CSVプレビュー読み込みエラー ({f}): {e}")
                file_info['lat_col'] = st.text_input(f"{f} の緯度カラム", value="lat", key=f"lat_folder_{f}")
                file_info['lon_col'] = st.text_input(f"{f} の経度カラム", value="lon", key=f"lon_folder_{f}")
            elif ext == ".geojson":
                try:
                    gdf = gpd.read_file(file_info["path"])
                    st.write(f"**{f} プレビュー:**")
                    st.dataframe(gdf.head())
                except Exception as e:
                    st.error(f"GeoJSONプレビュー読み込みエラー ({f}): {e}")
                file_info['lat_col'] = st.text_input(f"{f} の緯度カラム", value="lat", key=f"lat_folder_{f}")
                file_info['lon_col'] = st.text_input(f"{f} の経度カラム", value="lon", key=f"lon_folder_{f}")
            elif ext in [".tiff", ".tif"]:
                try:
                    with rasterio.open(file_info["path"]) as src:
                        meta = src.meta
                    st.write(f"**{f} メタデータ:**")
                    st.json(meta)
                except Exception as e:
                    st.error(f"TIFFメタデータ読み込みエラー ({f}): {e}")
                file_info['band'] = st.text_input(f"{f} の色分け用バンド", value="1", key=f"band_folder_{f}")
            selected_files.append(file_info)
    else:
        st.info("Inputフォルダが存在しません。")

    # 2. URLからの入力
    st.subheader("【2】URLからファイル入力")
    url_input = st.text_area("URLを入力してください（1行につき1つ）", key="url_input")
    if url_input:
        urls = [line.strip() for line in url_input.splitlines() if line.strip()]
        for url in urls:
            file_name = url.split("/")[-1]
            file_info = {"source": "url", "name": file_name, "url": url}
            ext = os.path.splitext(file_name)[1].lower()
            if ext == ".csv":
                try:
                    response = requests.get(url)
                    response.raise_for_status()
                    from io import StringIO
                    df = pd.read_csv(StringIO(response.text))
                    st.write(f"**{file_name} プレビュー:**")
                    st.dataframe(df.head())
                except Exception as e:
                    st.error(f"CSV URL プレビュー読み込みエラー ({file_name}): {e}")
                file_info['lat_col'] = st.text_input(f"{file_name} の緯度カラム", value="lat", key=f"lat_url_{file_name}")
                file_info['lon_col'] = st.text_input(f"{file_name} の経度カラム", value="lon", key=f"lon_url_{file_name}")
            elif ext == ".geojson":
                try:
                    response = requests.get(url)
                    response.raise_for_status()
                    from io import StringIO
                    gdf = gpd.read_file(StringIO(response.text))
                    st.write(f"**{file_name} プレビュー:**")
                    st.dataframe(gdf.head())
                except Exception as e:
                    st.error(f"GeoJSON URL プレビュー読み込みエラー ({file_name}): {e}")
                file_info['lat_col'] = st.text_input(f"{file_name} の緯度カラム", value="lat", key=f"lat_url_{file_name}")
                file_info['lon_col'] = st.text_input(f"{file_name} の経度カラム", value="lon", key=f"lon_url_{file_name}")
            elif ext in [".tiff", ".tif"]:
                try:
                    response = requests.get(url)
                    response.raise_for_status()
                    from rasterio.io import MemoryFile
                    with MemoryFile(response.content) as memfile:
                        with memfile.open() as src:
                            meta = src.meta
                    st.write(f"**{file_name} メタデータ:**")
                    st.json(meta)
                except Exception as e:
                    st.error(f"TIFF URL メタデータ読み込みエラー ({file_name}): {e}")
                file_info['band'] = st.text_input(f"{file_name} の色分け用バンド", value="1", key=f"band_url_{file_name}")
            selected_files.append(file_info)

    # 3. ファイルアップローダーからの入力
    st.subheader("【3】ファイルアップローダー")
    uploaded_files = st.file_uploader("ファイルをアップロード", type=["csv", "geojson", "tiff", "tif"], accept_multiple_files=True, key="file_uploader")
    if uploaded_files:
        for uploaded_file in uploaded_files:
            file_name = uploaded_file.name
            file_info = {"source": "upload", "name": file_name, "file": uploaded_file}
            ext = os.path.splitext(file_name)[1].lower()
            if ext == ".csv":
                try:
                    uploaded_file.seek(0)
                    df = pd.read_csv(uploaded_file)
                    st.write(f"**{file_name} プレビュー:**")
                    st.dataframe(df.head())
                except Exception as e:
                    st.error(f"アップロードCSVプレビュー読み込みエラー ({file_name}): {e}")
                file_info['lat_col'] = st.text_input(f"{file_name} の緯度カラム", value="lat", key=f"lat_upload_{file_name}")
                file_info['lon_col'] = st.text_input(f"{file_name} の経度カラム", value="lon", key=f"lon_upload_{file_name}")
            elif ext == ".geojson":
                try:
                    uploaded_file.seek(0)
                    gdf = gpd.read_file(uploaded_file)
                    st.write(f"**{file_name} プレビュー:**")
                    st.dataframe(gdf.head())
                except Exception as e:
                    st.error(f"アップロードGeoJSONプレビュー読み込みエラー ({file_name}): {e}")
                file_info['lat_col'] = st.text_input(f"{file_name} の緯度カラム", value="lat", key=f"lat_upload_{file_name}")
                file_info['lon_col'] = st.text_input(f"{file_name} の経度カラム", value="lon", key=f"lon_upload_{file_name}")
            elif ext in [".tiff", ".tif"]:
                try:
                    uploaded_file.seek(0)
                    with rasterio.open(uploaded_file) as src:
                        meta = src.meta
                    st.write(f"**{file_name} メタデータ:**")
                    st.json(meta)
                except Exception as e:
                    st.error(f"アップロードTIFFメタデータ読み込みエラー ({file_name}): {e}")
                file_info['band'] = st.text_input(f"{file_name} の色分け用バンド", value="1", key=f"band_upload_{file_name}")
            selected_files.append(file_info)

    st.write("### 選択されたファイル一覧:")
    if selected_files:
        for file_info in selected_files:
            st.write(f"{file_info['name']} ({file_info['source']})")
    else:
        st.write("ファイルが選択されていません。")
    
    # 選択結果をセッションステートに保存
    st.session_state["selected_files"] = selected_files

def display_dashboard(selected_files):
    st.header("ダッシュボード表示画面")
    st.write("以下の地図上に、選択されたデータを表示します。")
    
    # foliumで地図を初期化（例：日本付近を中心に表示）
    m = folium.Map(location=[36, 138], zoom_start=5)
    
    # 選択された各ファイルについて処理
    for file_info in selected_files:
        name = file_info["name"]
        ext = os.path.splitext(name)[1].lower()
        
        if file_info["source"] == "folder":
            file_path = file_info["path"]
            if ext == ".csv":
                try:
                    df = pd.read_csv(file_path)
                    # CSVに"lat"と"lon"のカラムがある場合、各行をマーカーで追加
                    if "lat" in df.columns and "lon" in df.columns:
                        for idx, row in df.iterrows():
                            folium.Marker(
                                location=[row["lat"], row["lon"]],
                                popup=f"{name}: {row.to_dict()}"
                            ).add_to(m)
                    else:
                        st.warning(f"CSVファイル {name} に 'lat' と 'lon' カラムが見つかりません。")
                except Exception as e:
                    st.error(f"CSVファイル {name} の読み込みエラー: {e}")
                    
            elif ext == ".geojson":
                try:
                    gdf = gpd.read_file(file_path)
                    folium.GeoJson(gdf).add_to(m)
                except Exception as e:
                    st.error(f"GeoJSONファイル {name} の読み込みエラー: {e}")
                    
            elif ext in [".tiff", ".tif"]:
                st.info(f"TIFFファイル {name} の地図上へのオーバーレイは現状実装されていません。")
        
        elif file_info["source"] == "url":
            url = file_info["url"]
            if ext == ".csv":
                try:
                    df = pd.read_csv(url)
                    if "lat" in df.columns and "lon" in df.columns:
                        for idx, row in df.iterrows():
                            folium.Marker(
                                location=[row["lat"], row["lon"]],
                                popup=f"{name}: {row.to_dict()}"
                            ).add_to(m)
                    else:
                        st.warning(f"CSVファイル {name} に 'lat' と 'lon' カラムが見つかりません。")
                except Exception as e:
                    st.error(f"CSV URL {url} の読み込みエラー: {e}")
                    
            elif ext == ".geojson":
                try:
                    gdf = gpd.read_file(url)
                    folium.GeoJson(gdf).add_to(m)
                except Exception as e:
                    st.error(f"GeoJSON URL {url} の読み込みエラー: {e}")
                    
            elif ext in [".tiff", ".tif"]:
                st.info(f"TIFFファイル {name} の地図上へのオーバーレイは現状実装されていません。")
        
        elif file_info["source"] == "upload":
            if ext == ".csv":
                try:
                    df = pd.read_csv(file_info["file"])
                    if "lat" in df.columns and "lon" in df.columns:
                        for idx, row in df.iterrows():
                            folium.Marker(
                                location=[row["lat"], row["lon"]],
                                popup=f"{name}: {row.to_dict()}"
                            ).add_to(m)
                    else:
                        st.warning(f"アップロードされたCSVファイル {name} に 'lat' と 'lon' カラムが見つかりません。")
                except Exception as e:
                    st.error(f"アップロードCSVファイル {name} の読み込みエラー: {e}")
                    
            elif ext == ".geojson":
                try:
                    # ファイルポインタを先頭に戻す
                    file_info["file"].seek(0)
                    gdf = gpd.read_file(file_info["file"])
                    folium.GeoJson(gdf).add_to(m)
                except Exception as e:
                    st.error(f"アップロードGeoJSONファイル {name} の読み込みエラー: {e}")
                    
            elif ext in [".tiff", ".tif"]:
                st.info(f"アップロードされたTIFFファイル {name} の地図上へのオーバーレイは現状実装されていません。")
    
    # 地図を表示
    st_folium(m)

def main():
    st.title("データ表示ダッシュボードアプリ")
    tab1, tab2 = st.tabs(["ファイル選択", "ダッシュボード表示"])
    
    with tab1:
        file_selection_screen()
    
    with tab2:
        if "selected_files" in st.session_state and st.session_state["selected_files"]:
            display_dashboard(st.session_state["selected_files"])
        else:
            st.warning("まずファイル選択タブでファイルを選択してください。")

if __name__ == "__main__":
    main()