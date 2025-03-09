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
from io import StringIO
import json

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
                # 既にセッション状態に値があれば、それを初期値として使用（なければデフォルト値 "lat" / "lon" を使用）
                lat_default = st.session_state.get(f"lat_column_{file_name}", "lat")
                lon_default = st.session_state.get(f"lon_column_{file_name}", "lon")
                file_info['lat_col'] = st.text_input(f"{file_name} の緯度カラム", value=lat_default, key=f"lat_column_{file_name}")
                file_info['lon_col'] = st.text_input(f"{file_name} の経度カラム", value=lon_default, key=f"lon_column_{file_name}")
            elif ext == ".geojson":
                try:
                    gdf = gpd.read_file(file_info["path"])
                    st.write(f"**{f} プレビュー:**")
                    st.dataframe(gdf.head())
                except Exception as e:
                    st.error(f"GeoJSONプレビュー読み込みエラー ({f}): {e}")
            elif ext in [".tiff", ".tif"]:
                try:
                    with rasterio.open(file_info["path"]) as src:
                        meta = src.meta
                    st.write(f"**{f} メタデータ:**")
                    st.json(meta)
                except Exception as e:
                    st.error(f"TIFFメタデータ読み込みエラー ({f}): {e}")
                file_info['band'] = st.text_input(f"{f} の色分け用バンド", value="1", key=f"band_folder_{f}")
            st.session_state.url_file_info.append(file_info)
    else:
        st.info("Inputフォルダが存在しません。")

    # 2. URLからの入力
    st.subheader("【2】URLからファイル入力")

    # -------------------------------------------------------
    # 1. セッションステートの初期化
    # -------------------------------------------------------
    # ここで複数ファイルの情報を保持するリストを用意する
    # url: 入力されたURL
    # loaded: ロード済かどうか (bool)
    # preview: 読み込んだDataFrame/GeoDataFrame/メタデータなど
    # lat_col, lon_col, band: カラム設定用（必要に応じて初期値を入れておく）
    if "url_entries" not in st.session_state:
        st.session_state["url_entries"] = [
            {
                "url": "",
                "loaded": False,
                "preview": None,
                "lat_col": "lat",
                "lon_col": "lon",
                "band": "1",
            }
        ]

    # -------------------------------------------------------
    # 2. URL入力欄とファイル読み込みのロジック
    # -------------------------------------------------------
    # url_entriesリストを順番に処理する。最後のURLが読み込み済みの場合、新しいURL入力欄を追加する。
    for i, entry in enumerate(st.session_state["url_entries"]):
        st.write(f"#### ファイル {i+1} のURL入力")

        # URL入力欄
        url_input = st.text_input(
            "URLを入力してください",
            key=f"url_input_{i}",  # キーをユニークに
            value=entry["url"]
        )

        # “読み込み”ボタン
        if not entry["loaded"] and st.button("読み込み", key=f"load_url_{i}"):
            # URLをセッションステートにも反映
            st.session_state["url_entries"][i]["url"] = url_input
            if url_input:
                file_name = url_input.split("/")[-1]
                ext = os.path.splitext(file_name)[1].lower()

                # -------------------------------------------------------
                # 2-1. ファイルの種類毎に読み込み
                # -------------------------------------------------------
                try:
                    with st.spinner(f"{file_name} を読み込み中..."):
                        response = requests.get(url_input, stream=True)

                        # ステータスコードチェック
                        if response.status_code == 200:
                            st.success(f"{file_name} へのアクセス成功（Status: {response.status_code}）")
                        else:
                            st.error(f"{file_name} へのアクセス拒否（Status: {response.status_code}）")
                        response.raise_for_status()

                        # ダウンロード進捗
                        total_size = int(response.headers.get("content-length", 0))
                        data_chunks = []
                        bytes_downloaded = 0
                        chunk_size = 1024

                        # ファイルサイズが不明かどうかで処理を分ける
                        if total_size == 0:
                            st.warning("ファイルサイズが不明なため、進捗表示はスキップします。")
                            data_chunks.append(response.content)
                        else:
                            progress_bar = st.progress(0)
                            for chunk in response.iter_content(chunk_size=chunk_size):
                                if chunk:
                                    data_chunks.append(chunk)
                                    bytes_downloaded += len(chunk)
                                    progress = int(min(bytes_downloaded / total_size, 1.0) * 100)
                                    progress_bar.progress(progress)

                        # -------------------------------------------------------
                        # 2-2. 取得データの読み込み処理
                        # -------------------------------------------------------
                        if ext == ".csv":
                            csv_data = b"".join(data_chunks).decode("utf-8")
                            df = pd.read_csv(StringIO(csv_data))
                            st.success(f"{file_name} の読み込みが完了しました。")
                            st.write(f"**{file_name} プレビュー:**")
                            st.dataframe(df.head())
                            st.session_state["url_entries"][i]["preview"] = df

                        elif ext == ".geojson":
                            geojson_data = b"".join(data_chunks).decode("utf-8")
                            geojson_dict = json.loads(geojson_data)
                            gdf = gpd.GeoDataFrame.from_features(geojson_dict["features"])
                            st.success(f"{file_name} の読み込みが完了しました。")
                            st.write(f"**{file_name} プレビュー:**")
                            st.dataframe(gdf.head())
                            st.session_state["url_entries"][i]["preview"] = gdf

                        elif ext in [".tiff", ".tif"]:
                            tiff_data = b"".join(data_chunks)
                            with MemoryFile(tiff_data) as memfile:
                                with memfile.open() as src:
                                    meta = src.meta
                            st.success(f"{file_name} の読み込みが完了しました。")
                            st.write(f"**{file_name} メタデータ:**")
                            st.json(meta)
                            st.session_state["url_entries"][i]["preview"] = meta

                        else:
                            st.error(f"対応していない拡張子です: {ext}")
                            st.stop()

                    # ロード完了フラグ
                    st.session_state["url_entries"][i]["loaded"] = True

                except Exception as e:
                    st.error(f"ファイル読み込みエラー ({file_name}): {e}")

        # -------------------------------------------------------
        # 3. 既に読み込み済みならプレビュー表示 & カラム指定表示
        # -------------------------------------------------------
        if entry["loaded"]:
            file_name = entry["url"].split("/")[-1]
            ext = os.path.splitext(file_name)[1].lower()
            st.write(f"**{file_name} の再プレビュー:**")

            preview_data = st.session_state["url_entries"][i]["preview"]
            if isinstance(preview_data, pd.DataFrame):
                st.dataframe(preview_data.head())
            elif isinstance(preview_data, gpd.GeoDataFrame):
                st.dataframe(preview_data.head())
            else:
                # TIFFなどメタデータの場合
                st.json(preview_data)

            # CSVの場合は緯度経度カラム、TIFFの場合はバンドなどを入力
            if ext == ".csv":
                lat_col_key = f"lat_column_{i}"
                lon_col_key = f"lon_column_{i}"
                lat_default = st.session_state["url_entries"][i].get("lat_col", "lat")
                lon_default = st.session_state["url_entries"][i].get("lon_col", "lon")

                st.session_state["url_entries"][i]["lat_col"] = st.text_input(
                    f"{file_name} の緯度カラム", value=lat_default, key=lat_col_key
                )
                lat_default = st.session_state["url_entries"][i].get("lat_col", "error")
                st.success(f"{file_name} の緯度カラムを{lat_default} に設定しました。")
                st.session_state["url_entries"][i]["lon_col"] = st.text_input(
                    f"{file_name} の経度カラム", value=lon_default, key=lon_col_key
                )
                lon_default = st.session_state["url_entries"][i].get("lon_col", "lon")
                st.success(f"{file_name} の経度カラムを{lon_default} に設定しました。")

            elif ext in [".tiff", ".tif"]:
                band_key = f"band_url_{i}"
                band_default = st.session_state["url_entries"][i].get("band", "1")
                st.session_state["url_entries"][i]["band"] = st.text_input(
                    f"{file_name} の色分け用バンド", value=band_default, key=band_key
                )
                band_default = st.session_state["url_entries"][i].get("band", "error")
                st.success(f"{file_name} の色分け用バンドを{band_default} に設定しました。")

    # -------------------------------------------------------
    # 4. “次のファイル入力”の自動追加
    #    最後のエントリがloaded=Trueになったら、新規URL入力欄を追加する
    # -------------------------------------------------------
    last_index = len(st.session_state["url_entries"]) - 1
    if st.session_state["url_entries"][last_index]["loaded"]:
        # すでに別のURL欄が追加済みでなければ追加
        # （例：連続再実行で2つ以上増えないようにチェックする）
        # 下のように単純に追加すると、読み込むたび無限に増えるので
        # 「まだ空のURL欄を持つエントリが存在しない場合のみ追加」などのチェックを入れる
        empty_urls = [
            ent for ent in st.session_state["url_entries"] 
            if ent["url"] == "" and not ent["loaded"]
        ]
        if not empty_urls:
            st.session_state["url_entries"].append(
                {
                    "url": "",
                    "loaded": False,
                    "preview": None,
                    "lat_col": "lat",
                    "lon_col": "lon",
                    "band": "1",
                }
            )

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
                    # 既にセッション状態に値があれば、それを初期値として使用（なければデフォルト値 "lat" / "lon" を使用）
                    lat_default = st.session_state.get(f"lat_column_{file_name}", "lat")
                    lon_default = st.session_state.get(f"lon_column_{file_name}", "lon")
                    file_info['lat_col'] = st.text_input(f"{file_name} の緯度カラム", value=lat_default, key=f"lat_column_{file_name}")
                    file_info['lon_col'] = st.text_input(f"{file_name} の経度カラム", value=lon_default, key=f"lon_column_{file_name}")
                except Exception as e:
                    st.error(f"アップロードCSVプレビュー読み込みエラー ({file_name}): {e}")
            elif ext == ".geojson":
                try:
                    uploaded_file.seek(0)
                    gdf = gpd.read_file(uploaded_file)
                    st.write(f"**{file_name} プレビュー:**")
                    st.dataframe(gdf.head())
                except Exception as e:
                    st.error(f"アップロードGeoJSONプレビュー読み込みエラー ({file_name}): {e}")
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
            st.session_state.url_file_info.append(file_info)

    # 選択されたファイルの一覧
    if "url_file_info" in st.session_state and st.session_state.url_file_info:
        st.write("### 選択されたファイル一覧:")
        for file_info in st.session_state.url_file_info:
            st.write(f"{file_info['name']} ({file_info['source']})")
            st.write(f"file_info: {file_info}")
    else:
        st.write("ファイルが選択されていません。")

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
    # セッション変数 "url_file_info" が存在しなければ初期化
    if "url_file_info" not in st.session_state:
        st.session_state.url_file_info = []
    
    tab1, tab2 = st.tabs(["ファイル選択", "ダッシュボード表示"])
    
    with tab1:
        file_selection_screen()
    
    with tab2:
        if st.session_state.url_file_info:
            display_dashboard(st.session_state.url_file_info)
        else:
            st.warning("まずファイル選択タブでファイルを選択してください。")

if __name__ == "__main__":
    main()