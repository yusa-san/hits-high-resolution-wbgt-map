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
    st.header("ファイル選択画面")
    selected_files = []
    
    # ① inputフォルダ内からの選択
    st.subheader("【1】Inputフォルダからファイル選択")
    input_folder = "input"
    if os.path.isdir(input_folder):
        folder_files = os.listdir(input_folder)
        # 対応する拡張子のみフィルタ
        supported_exts = ['.csv', '.geojson', '.tiff', '.tif']
        folder_files = [f for f in folder_files if any(f.lower().endswith(ext) for ext in supported_exts)]
        folder_selected = st.multiselect("Inputフォルダ内のファイル", folder_files)
        for f in folder_selected:
            selected_files.append({
                "source": "folder",
                "name": f,
                "path": os.path.join(input_folder, f)
            })
    else:
        st.info("Inputフォルダが存在しません。")
    
    # ② URLからの入力
    st.subheader("【2】URLからファイル入力")
    url_input = st.text_area("URLを入力してください（1行につき1つ）")
    if url_input:
        urls = [line.strip() for line in url_input.splitlines() if line.strip()]
        for u in urls:
            # URLの末尾部分をファイル名として利用
            file_name = u.split("/")[-1]
            selected_files.append({
                "source": "url",
                "name": file_name,
                "url": u
            })
    
    # ③ ファイルアップローダーからの入力
    st.subheader("【3】ファイルアップローダー")
    uploaded_files = st.file_uploader("ファイルをアップロード", type=["csv", "geojson", "tiff", "tif"], accept_multiple_files=True)
    if uploaded_files:
        for uploaded_file in uploaded_files:
            selected_files.append({
                "source": "upload",
                "name": uploaded_file.name,
                "file": uploaded_file  # BytesIOオブジェクト
            })
    
    st.write("選択されたファイル一覧:")
    if selected_files:
        for idx, file_info in enumerate(selected_files):
            st.write(f"### {file_info['name']} ({file_info['source']})")
            ext = os.path.splitext(file_info['name'])[1].lower()
            if ext in [".csv"]:
                try:
                    if file_info["source"] == "folder":
                        df = pd.read_csv(file_info["path"])
                    elif file_info["source"] == "url":
                        df = pd.read_csv(file_info["url"])
                    elif file_info["source"] == "upload":
                        file_info["file"].seek(0)
                        df = pd.read_csv(file_info["file"])
                    st.dataframe(df.head())
                except Exception as e:
                    st.error(f"CSVプレビュー読み込みエラー: {e}")
                file_info['lat_col'] = st.text_input(f"{file_info['name']} の緯度カラム", value="lat", key=f"lat_{idx}")
                file_info['lon_col'] = st.text_input(f"{file_info['name']} の経度カラム", value="lon", key=f"lon_{idx}")
            elif ext in [".geojson"]:
                try:
                    if file_info["source"] == "folder":
                        gdf = gpd.read_file(file_info["path"])
                    elif file_info["source"] == "url":
                        gdf = gpd.read_file(file_info["url"])
                    elif file_info["source"] == "upload":
                        file_info["file"].seek(0)
                        gdf = gpd.read_file(file_info["file"])
                    st.dataframe(gdf.head())
                except Exception as e:
                    st.error(f"GeoJSONプレビュー読み込みエラー: {e}")
                file_info['lat_col'] = st.text_input(f"{file_info['name']} の緯度カラム", value="lat", key=f"lat_{idx}")
                file_info['lon_col'] = st.text_input(f"{file_info['name']} の経度カラム", value="lon", key=f"lon_{idx}")
            elif ext in [".tiff", ".tif"]:
                try:
                    if file_info["source"] == "folder":
                        with rasterio.open(file_info["path"]) as src:
                            meta = src.meta
                    elif file_info["source"] == "url":
                        response = requests.get(file_info["url"])
                        response.raise_for_status()
                        with MemoryFile(response.content) as memfile:
                            with memfile.open() as src:
                                meta = src.meta
                    elif file_info["source"] == "upload":
                        file_info["file"].seek(0)
                        with rasterio.open(file_info["file"]) as src:
                            meta = src.meta
                    st.json(meta)
                except Exception as e:
                    st.error(f"ラスターデータのメタデータ読み込みエラー: {e}")
                file_info['band'] = st.text_input(f"{file_info['name']} の色分け用バンド", value="1", key=f"band_{idx}")
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