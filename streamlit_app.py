import os
import streamlit as st
import pandas as pd
import geopandas as gpd
import rasterio
import matplotlib.pyplot as plt
import folium
from streamlit_folium import folium_static

st.title("インタラクティブデータ表示ダッシュボード")

# 指定のinputフォルダー内のファイル一覧を取得
INPUT_FOLDER = "./input"
all_files = os.listdir(INPUT_FOLDER)

# サポートする拡張子をフィルタ
supported_exts = ['.csv', '.geojson', '.tiff', '.tif']
files = [f for f in all_files if any(f.lower().endswith(ext) for ext in supported_exts)]

if not files:
    st.error("指定されたinputフォルダーにサポートされているファイルが見つかりません。")
else:
    # ファイル選択用のセレクトボックス（サイドバーなどで配置可能）
    selected_file = st.selectbox("表示するファイルを選択してください", files)
    file_path = os.path.join(INPUT_FOLDER, selected_file)
    ext = os.path.splitext(selected_file)[1].lower()

    # CSVの場合
    if ext == ".csv":
        st.subheader("CSVデータ")
        try:
            df = pd.read_csv(file_path)
            st.dataframe(df)
        except Exception as e:
            st.error(f"CSVファイルの読み込み中にエラーが発生しました: {e}")

    # GeoJSONの場合
    elif ext == ".geojson":
        st.subheader("GeoJSONデータ")
        try:
            gdf = gpd.read_file(file_path)
            st.dataframe(gdf)
            
            # マップ表示：最初のジオメトリの中心座標を利用
            if not gdf.empty and "geometry" in gdf:
                centroid = gdf.geometry.centroid.iloc[0]
                m = folium.Map(location=[centroid.y, centroid.x], zoom_start=10)
                folium.GeoJson(gdf).add_to(m)
                st.subheader("GeoJSONデータのマップ表示")
                folium_static(m)
        except Exception as e:
            st.error(f"GeoJSONファイルの読み込み中にエラーが発生しました: {e}")

    # TIFF (またはTIF)の場合
    elif ext in [".tiff", ".tif"]:
        st.subheader("TIFFデータ")
        try:
            with rasterio.open(file_path) as src:
                image = src.read(1)  # 1バンド目を読み込み
                fig, ax = plt.subplots(figsize=(8, 6))
                ax.imshow(image, cmap="gray")
                ax.set_title("TIFFデータ表示")
                ax.axis("off")
                st.pyplot(fig)
        except Exception as e:
            st.error(f"TIFFファイルの読み込み中にエラーが発生しました: {e}")

    else:
        st.warning("サポートされていないファイル形式です。")