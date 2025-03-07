import os
import streamlit as st
import pandas as pd
import geopandas as gpd
import rasterio
import matplotlib.pyplot as plt
import folium
from streamlit_folium import folium_static

st.title("インタラクティブデータ表示ダッシュボード")

INPUT_FOLDER = "./input"

if os.path.isdir(INPUT_FOLDER):
    # inputフォルダー内のファイル一覧を取得
    all_files = os.listdir(INPUT_FOLDER)
    supported_exts = ['.csv', '.geojson', '.tiff', '.tif']
    files = [f for f in all_files if any(f.lower().endswith(ext) for ext in supported_exts)]
    
    if not files:
        st.error("inputフォルダーにサポートされているファイルが見つかりません。")
    else:
        selected_file = st.selectbox("表示するファイルを選択してください", files)
        file_path = os.path.join(INPUT_FOLDER, selected_file)
        ext = os.path.splitext(selected_file)[1].lower()
        
        if ext == ".csv":
            try:
                df = pd.read_csv(file_path)
                st.subheader("CSVデータ")
                st.dataframe(df)
            except Exception as e:
                st.error(f"CSVファイルの読み込み中にエラーが発生しました: {e}")
                
        elif ext == ".geojson":
            try:
                gdf = gpd.read_file(file_path)
                st.subheader("GeoJSONデータ")
                st.dataframe(gdf)
                if not gdf.empty and "geometry" in gdf:
                    centroid = gdf.geometry.centroid.iloc[0]
                    m = folium.Map(location=[centroid.y, centroid.x], zoom_start=10)
                    folium.GeoJson(gdf).add_to(m)
                    st.subheader("GeoJSONデータのマップ表示")
                    folium_static(m)
            except Exception as e:
                st.error(f"GeoJSONファイルの読み込み中にエラーが発生しました: {e}")
                
        elif ext in [".tiff", ".tif"]:
            try:
                with rasterio.open(file_path) as src:
                    image = src.read(1)
                    fig, ax = plt.subplots(figsize=(8, 6))
                    ax.imshow(image, cmap="gray")
                    ax.set_title("TIFFデータ表示")
                    ax.axis("off")
                    st.pyplot(fig)
            except Exception as e:
                st.error(f"TIFFファイルの読み込み中にエラーが発生しました: {e}")
                
        else:
            st.warning("サポートされていないファイル形式です。")
else:
    st.warning("inputフォルダーが存在しません。ファイルアップロード機能を使用してください。")
    uploaded_file = st.file_uploader("表示するファイルをアップロードしてください", type=["csv", "geojson", "tiff", "tif"])
    if uploaded_file is not None:
        ext = os.path.splitext(uploaded_file.name)[1].lower()
        
        if ext == ".csv":
            try:
                df = pd.read_csv(uploaded_file)
                st.subheader("CSVデータ")
                st.dataframe(df)
            except Exception as e:
                st.error(f"CSVファイルの読み込み中にエラーが発生しました: {e}")
                
        elif ext == ".geojson":
            try:
                gdf = gpd.read_file(uploaded_file)
                st.subheader("GeoJSONデータ")
                st.dataframe(gdf)
                if not gdf.empty and "geometry" in gdf:
                    centroid = gdf.geometry.centroid.iloc[0]
                    m = folium.Map(location=[centroid.y, centroid.x], zoom_start=10)
                    folium.GeoJson(gdf).add_to(m)
                    st.subheader("GeoJSONデータのマップ表示")
                    folium_static(m)
            except Exception as e:
                st.error(f"GeoJSONファイルの読み込み中にエラーが発生しました: {e}")
                
        elif ext in [".tiff", ".tif"]:
            try:
                with rasterio.open(uploaded_file) as src:
                    image = src.read(1)
                    fig, ax = plt.subplots(figsize=(8, 6))
                    ax.imshow(image, cmap="gray")
                    ax.set_title("TIFFデータ表示")
                    ax.axis("off")
                    st.pyplot(fig)
            except Exception as e:
                st.error(f"TIFFファイルの読み込み中にエラーが発生しました: {e}")
        else:
            st.error("サポートされていないファイル形式です。")