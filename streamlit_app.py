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
    # キャッシュ用の状態を初期化（URL入力用）
    if "url_file_info" not in st.session_state:
        st.session_state.url_file_info = []
    if "url_file_preview" not in st.session_state:
        st.session_state.url_file_preview = {}

    url_input = st.text_input("URLを入力してください", key="url_input")
    if st.button("読み込み", key="load_url"):
        # st.success(f"読み込みボタンが押されました") # debug
        if url_input:
            file_name = url_input.split("/")[-1]
            file_info = {"source": "url", "name": file_name, "url": url_input}
            ext = os.path.splitext(file_name)[1].lower()
            # st.success(f"{ext}の{file_name}を読み込みます。") # debug
            # CSVの場合
            if ext == ".csv":
                try:
                    # st.success(f"csvのtryの中に入りました")
                    with st.spinner(f"{file_name} を読み込み中..."):
                        response = requests.get(url_input, stream=True)
                        # アクセス結果のチェック
                        if response.status_code == 200:
                            st.success(f"{file_name} へのアクセス成功（Status: {response.status_code}）")
                        else:
                            st.error(f"{file_name} へのアクセス拒否（Status: {response.status_code}）")
                        response.raise_for_status()
                        total_size = int(response.headers.get('content-length', 0))
                        data_chunks = []
                        bytes_downloaded = 0
                        if total_size == 0:
                            st.warning("ファイルサイズが不明なため、進捗表示はスキップします。")
                            data_chunks.append(response.content)
                        else:
                            progress_bar = st.progress(0)
                            chunk_size = 1024
                            for chunk in response.iter_content(chunk_size=chunk_size):
                                if chunk:
                                    data_chunks.append(chunk)
                                    bytes_downloaded += len(chunk)
                                    progress = int(min(bytes_downloaded / total_size, 1.0) * 100)
                                    progress_bar.progress(progress)
                        csv_data = b"".join(data_chunks).decode("utf-8")
                        from io import StringIO
                        df = pd.read_csv(StringIO(csv_data))
                    st.success(f"{file_name} の読み込みが完了しました。")
                    st.write(f"**{file_name} プレビュー:**")
                    st.dataframe(df.head())
                    st.session_state.url_file_preview[url_input] = df # 読み込んだCSVデータをキャッシュに保存
                    file_info['lat_col'] = st.text_input(f"{file_name} の緯度カラム", value="lat", key=f"lat_url_{file_name}")
                    file_info['lon_col'] = st.text_input(f"{file_name} の経度カラム", value="lon", key=f"lon_url_{file_name}")
                except Exception as e:
                    st.error(f"CSV URL プレビュー読み込みエラー ({file_name}): {e}")
            # GeoJSONの場合
            elif ext == ".geojson":
                try:
                    # st.success(f"geojsonのtryの中に入りました")
                    with st.spinner(f"{file_name} を読み込み中..."):
                        response = requests.get(url_input, stream=True)
                        if response.status_code == 200:
                            st.success(f"{file_name} へのアクセス成功（Status: {response.status_code}）")
                        else:
                            st.error(f"{file_name} へのアクセス拒否（Status: {response.status_code}）")
                        response.raise_for_status()
                        total_size = int(response.headers.get('content-length', 0))
                        data_chunks = []
                        bytes_downloaded = 0
                        if total_size == 0:
                            st.warning("ファイルサイズが不明なため、進捗表示はスキップします。")
                            data_chunks.append(response.content)
                        else:
                            progress_bar = st.progress(0)
                            chunk_size = 1024
                            for chunk in response.iter_content(chunk_size=chunk_size):
                                if chunk:
                                    data_chunks.append(chunk)
                                    bytes_downloaded += len(chunk)
                                    progress = int(min(bytes_downloaded / total_size, 1.0) * 100)
                                    progress_bar.progress(progress)
                        geojson_data = b"".join(data_chunks).decode("utf-8")
                        import json
                        geojson_dict = json.loads(geojson_data) # geojson_data はすでに文字列として取得済み
                        gdf = gpd.GeoDataFrame.from_features(geojson_dict["features"])
                    st.success(f"{file_name} の読み込みが完了しました。")
                    st.write(f"**{file_name} プレビュー:**")
                    st.dataframe(gdf.head())
                    st.session_state.url_file_preview[url_input] = gdf # 読み込んだgeojsonデータをキャッシュに保存
                    file_info['lat_col'] = st.text_input(f"{file_name} の緯度カラム", value="lat", key=f"lat_url_{file_name}")
                    file_info['lon_col'] = st.text_input(f"{file_name} の経度カラム", value="lon", key=f"lon_url_{file_name}")
                except Exception as e:
                    st.error(f"GeoJSON URL プレビュー読み込みエラー ({file_name}): {e}")
            # TIFFの場合
            elif ext in [".tiff", ".tif"]:
                try:
                    # st.success(f"tiffまたはtifのtryの中に入りました")
                    with st.spinner(f"{file_name} を読み込み中..."):
                        response = requests.get(url_input, stream=True)
                        if response.status_code == 200:
                            st.success(f"{file_name} へのアクセス成功（Status: {response.status_code}）")
                        else:
                            st.error(f"{file_name} へのアクセス拒否（Status: {response.status_code}）")
                        response.raise_for_status()
                        total_size = int(response.headers.get('content-length', 0))
                        data_chunks = []
                        bytes_downloaded = 0
                        if total_size == 0:
                            st.warning("ファイルサイズが不明なため、進捗表示はスキップします。")
                            data_chunks.append(response.content)
                        else:
                            progress_bar = st.progress(0)
                            chunk_size = 1024
                            for chunk in response.iter_content(chunk_size=chunk_size):
                                if chunk:
                                    data_chunks.append(chunk)
                                    bytes_downloaded += len(chunk)
                                    progress = int(min(bytes_downloaded / total_size, 1.0) * 100)
                                    progress_bar.progress(progress)
                        tiff_data = b"".join(data_chunks)
                        from rasterio.io import MemoryFile
                        with MemoryFile(tiff_data) as memfile:
                            with memfile.open() as src:
                                meta = src.meta
                    st.success(f"{file_name} の読み込みが完了しました。")
                    st.write(f"**{file_name} メタデータ:**")
                    st.json(meta)
                    st.session_state.url_file_preview[url_input] = meta # 読み込んだメタデータをキャッシュに保存
                    file_info['band'] = st.text_input(f"{file_name} の色分け用バンド", value="1", key=f"band_url_{file_name}")
                except Exception as e:
                    st.error(f"TIFF URL メタデータ読み込みエラー ({file_name}): {e}")
            st.session_state.url_file_info.append(file_info)

    # 既に読み込み済みなら再表示
    if url_input and url_input in st.session_state.url_file_preview:
        preview = st.session_state.url_file_preview[url_input]
        st.write(f"**{file_name} の再プレビュー:**")
        if isinstance(preview, pd.DataFrame):
            st.dataframe(preview.head())
        elif isinstance(preview, gpd.GeoDataFrame):
            st.dataframe(preview.head())
        else:
            st.json(preview)

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
                    # file_infoで指定された緯度・経度カラムを取得（デフォルトは"lat", "lon"）
                    lat_col = file_info.get('lat_col', 'lat')
                    lon_col = file_info.get('lon_col', 'lon')
                    if lat_col in df.columns and lon_col in df.columns:
                        for idx, row in df.iterrows():
                            folium.Marker(
                                location=[row[lat_col], row[lon_col]],
                                popup=f"{name}: {row.to_dict()}"
                            ).add_to(m)
                    else:
                        st.warning(f"CSVファイル {name} に指定された緯度カラム '{lat_col}' と経度カラム '{lon_col}' が見つかりません。")
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