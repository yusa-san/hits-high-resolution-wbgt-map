import os
import streamlit as st
import pandas as pd
import geopandas as gpd
import requests
import rasterio
from rasterio.io import MemoryFile
import matplotlib.pyplot as plt
import matplotlib.cm as cm
import matplotlib.colors as mcolors
import folium
from streamlit_folium import st_folium
from io import StringIO
import json
import plotly.express as px
import plotly.graph_objects as go
import pydeck as pdk
import numpy as np

st.set_page_config(layout="wide")

def file_selection_screen():
    st.header("ファイル選択")

    # 全体の再読み込みボタン
    if st.button("再読み込み"):
        st.rerun()

    # 1. Inputフォルダからの選択
    # セッション変数 "folder_entries" の初期化（もし存在しなければ）
    if "folder_entries" not in st.session_state:
        st.session_state["folder_entries"] = []

    st.subheader("【1】Inputフォルダからファイル選択")
    input_folder = "input"
    if os.path.isdir(input_folder):
        folder_files = os.listdir(input_folder)
        supported_exts = ['.csv', '.geojson', '.tiff', '.tif']
        folder_files = [f for f in folder_files if any(f.lower().endswith(ext) for ext in supported_exts)]
        folder_selected = st.multiselect("Inputフォルダ内のファイル", folder_files)
        for file_name in folder_selected:
            # 各要素の初期値を file_info にまとめて設定
            file_info = {
                "source": "folder",
                "name": file_name,
                "path": os.path.join(input_folder, file_name),
                "loaded": False,
                "lat_col": st.session_state.get(f"lat_column_{file_name}", "lat"),
                "lon_col": st.session_state.get(f"lon_column_{file_name}", "lon"),
                "band": st.session_state.get(f"band_folder_{file_name}", 1),
                "preview": None,
            }
            ext = os.path.splitext(file_name)[1].lower()
            if ext == ".csv":
                try:
                    df = pd.read_csv(file_info["path"])
                    file_info["preview"] = df
                    file_info["loaded"] = True
                except Exception as e:
                    st.error(f"CSVプレビュー読み込みエラー ({file_name}): {e}")
                # テキスト入力でユーザーが変更した値を反映（セッションの初期値として利用）
                # file_info['lat_col'] = st.text_input(f"{file_name} の緯度カラム", value=file_info["lat_col"], key=f"lat_column_{file_name}")
                # st.success(f"{file_name} の緯度カラムを{file_info['lat_col']} に設定しました。")
                # file_info['lon_col'] = st.text_input(f"{file_name} の経度カラム", value=file_info["lon_col"], key=f"lon_column_{file_name}")
                # st.success(f"{file_name} の経度カラムを{file_info['lon_col']} に設定しました。")
            elif ext == ".geojson":
                try:
                    gdf = gpd.read_file(file_info["path"])
                    file_info["preview"] = gdf
                    file_info["loaded"] = True
                except Exception as e:
                    st.error(f"GeoJSONプレビュー読み込みエラー ({file_name}): {e}")
            elif ext in [".tiff", ".tif"]:
                try:
                    with rasterio.open(file_info["path"]) as src:
                        meta = src.meta
                    file_info["preview"] = meta
                    file_info["loaded"] = True
                except Exception as e:
                    st.error(f"TIFFメタデータ読み込みエラー ({file_name}): {e}")
                # file_info['band'] = st.text_input(f"{file_name} の色分け用バンド", value=file_info["band"], key=f"band_folder_{file_name}")

            # file_infoを追加
            if not any(entry['name'] == file_info['name'] for entry in st.session_state["folder_entries"]):
                st.session_state["folder_entries"].append(file_info)

        # プレビューとカラムの設定
        for i, file_info in enumerate(st.session_state["folder_entries"]):
            if file_info["loaded"]:
                file_name = file_info["name"]
                ext = os.path.splitext(file_name)[1].lower()
                st.write(f"**{file_name} プレビュー:**")
                preview_data = file_info["preview"]
                if isinstance(preview_data, pd.DataFrame):
                    st.dataframe(preview_data.head())
                elif isinstance(preview_data, gpd.GeoDataFrame):
                    st.dataframe(preview_data.head())
                else:
                    st.json(preview_data)
                # CSVの場合は緯度経度カラム、TIFFの場合はバンドなどを入力
                if ext == ".csv":
                    lat_col_key = f"lat_column_{file_name}"
                    lon_col_key = f"lon_column_{file_name}"
                    lat_default = st.session_state.get(f"lat_column_{file_name}", "lat")
                    lon_default = st.session_state.get(f"lon_column_{file_name}", "lon")
                    st.session_state["folder_entries"][i]["lat_col"] = st.text_input(
                        f"{file_name} の緯度カラム", value=lat_default, key=lat_col_key
                    )
                    st.success(f"{file_name} の緯度カラムを{lat_default} に設定しました。")
                    st.session_state["folder_entries"][i]["lon_col"] = st.text_input(
                        f"{file_name} の経度カラム", value=lon_default, key=lon_col_key
                    )
                    st.success(f"{file_name} の経度カラムを{lon_default} に設定しました。")
                elif ext in [".tiff", ".tif"]:
                    band_key = f"band_folder_{file_name}"
                    band_default = st.session_state.get(f"band_folder_{file_name}", 1)
                    st.session_state["folder_entries"][i]["band"] = st.text_input(
                        f"{file_name} の色分け用バンド", value=band_default, key=band_key
                    )
                    st.success(f"{file_name} の色分け用バンドを{band_default} に設定しました。")

    else:
        st.info("Inputフォルダが存在しません。")

    # 2. URLからの入力
    st.subheader("【2】URLからファイル入力")

    # 1_セッションステートの初期化
    if "url_entries" not in st.session_state:
        # loaded: ロード済かどうか (bool)
        # preview: 読み込んだDataFrame/GeoDataFrame/メタデータなど
        # lat_col, lon_col, band: カラム設定用（必要に応じて初期値を入れておく）
        st.session_state["url_entries"] = [
            {
                "source": "url",
                "name": "",
                "url": "",
                "loaded": False,
                "lat_col": "lat",
                "lon_col": "lon",
                "band": 1,
                "preview": None,
            }
        ]
    # 2_URL入力欄とファイル読み込みのロジック # url_entriesリストを順番に処理する
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
                st.session_state["url_entries"][i]["name"] = file_name
                ext = os.path.splitext(file_name)[1].lower()
                # 2-1_ファイルの種類毎に読み込み
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
                        # 2-2. 取得データの読み込み処理
                        if ext == ".csv":
                            csv_data = b"".join(data_chunks).decode("utf-8")
                            df = pd.read_csv(StringIO(csv_data))
                            st.success(f"{file_name} の読み込みが完了しました。")
                            st.session_state["url_entries"][i]["preview"] = df
                        elif ext == ".geojson":
                            geojson_data = b"".join(data_chunks).decode("utf-8")
                            geojson_dict = json.loads(geojson_data)
                            gdf = gpd.GeoDataFrame.from_features(geojson_dict["features"])
                            st.success(f"{file_name} の読み込みが完了しました。")
                            st.session_state["url_entries"][i]["preview"] = gdf
                        elif ext in [".tiff", ".tif"]:
                            tiff_data = b"".join(data_chunks)
                            with MemoryFile(tiff_data) as memfile:
                                with memfile.open() as src:
                                    meta = src.meta
                            st.success(f"{file_name} の読み込みが完了しました。")
                            st.session_state["url_entries"][i]["preview"] = meta
                        else:
                            st.error(f"対応していない拡張子です: {ext}")
                            st.stop()
                    # ロード完了フラグ
                    st.session_state["url_entries"][i]["loaded"] = True
                except Exception as e:
                    st.error(f"ファイル読み込みエラー ({file_name}): {e}")
        # 3_既に読み込み済みならプレビュー表示 & カラム指定表示
        if entry["loaded"]:
            file_name = entry["url"].split("/")[-1]
            ext = os.path.splitext(file_name)[1].lower()
            st.write(f"**{file_name} のプレビュー:**")
            preview_data = st.session_state["url_entries"][i]["preview"]
            if isinstance(preview_data, pd.DataFrame):
                st.dataframe(preview_data.head())
            elif isinstance(preview_data, gpd.GeoDataFrame):
                st.dataframe(preview_data.head())
            else:
                st.json(preview_data)
            # CSVの場合は緯度経度カラム、TIFFの場合はバンドなどを入力
            if ext == ".csv":
                lat_col_key = f"lat_column_{file_name}"
                lon_col_key = f"lon_column_{file_name}"
                lat_default = st.session_state.get(f"lat_column_{file_name}", "lat")
                lon_default = st.session_state.get(f"lon_column_{file_name}", "lon")
                st.session_state["url_entries"][i]["lat_col"] = st.text_input(
                    f"{file_name} の緯度カラム", value=lat_default, key=lat_col_key
                )
                st.success(f"{file_name} の緯度カラムを{lat_default} に設定しました。")
                st.session_state["url_entries"][i]["lon_col"] = st.text_input(
                    f"{file_name} の経度カラム", value=lon_default, key=lon_col_key
                )
                st.success(f"{file_name} の経度カラムを{lon_default} に設定しました。")

            elif ext in [".tiff", ".tif"]:
                band_key = f"band_url_{file_name}"
                band_default = st.session_state.get(f"band_url_{file_name}", 1)
                st.session_state["url_entries"][i]["band"] = st.text_input(
                    f"{file_name} の色分け用バンド", value=band_default, key=band_key
                )
                st.success(f"{file_name} の色分け用バンドを{band_default} に設定しました。")
    # 4_“次のファイル入力”の自動追加
    #    最後のエントリがloaded=Trueになったら、新規URL入力欄を追加する
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
                    "source": "url",
                    "name": "",
                    "url": "",
                    "loaded": False,
                    "lat_col": "lat",
                    "lon_col": "lon",
                    "band": 1,
                    "preview": None,
                }
            )

    # 3. ファイルアップローダーからの入力
    # セッション変数 "upload_entries" の初期化（存在しなければ）
    if "upload_entries" not in st.session_state:
        st.session_state["upload_entries"] = []

    st.subheader("【3】ファイルアップローダー")
    uploaded_files = st.file_uploader("ファイルをアップロード", type=["csv", "geojson", "tiff", "tif"], accept_multiple_files=True, key="file_uploader")
    if uploaded_files:
        for uploaded_file in uploaded_files:
            file_name = uploaded_file.name
            # 各要素の初期値を設定して file_info を作成
            file_info = {
                "source": "upload",
                "name": file_name,
                "file": uploaded_file,
                "loaded": False,
                "lat_col": st.session_state.get(f"lat_column_{file_name}", "lat"),
                "lon_col": st.session_state.get(f"lon_column_{file_name}", "lon"),
                "band": st.session_state.get(f"band_upload_{file_name}", 1),
                "preview": None,
            }
            ext = os.path.splitext(file_name)[1].lower()
            if ext == ".csv":
                try:
                    uploaded_file.seek(0)
                    df = pd.read_csv(uploaded_file)
                    file_info["preview"] = df
                    file_info["loaded"] = True
                except Exception as e:
                    st.error(f"アップロードCSVプレビュー読み込みエラー ({file_name}): {e}")
                # file_info['lat_col'] = st.text_input(f"{file_name} の緯度カラム", value=file_info["lat_col"], key=f"lat_column_{file_name}")
                # file_info['lon_col'] = st.text_input(f"{file_name} の経度カラム", value=file_info["lon_col"], key=f"lon_column_{file_name}")
            elif ext == ".geojson":
                try:
                    uploaded_file.seek(0)
                    gdf = gpd.read_file(uploaded_file)
                    file_info["preview"] = gdf
                    file_info["loaded"] = True
                except Exception as e:
                    st.error(f"アップロードGeoJSONプレビュー読み込みエラー ({file_name}): {e}")
            elif ext in [".tiff", ".tif"]:
                try:
                    uploaded_file.seek(0)
                    with rasterio.open(uploaded_file) as src:
                        meta = src.meta
                    file_info["preview"] = meta
                    file_info["loaded"] = True
                except Exception as e:
                    st.error(f"アップロードTIFFメタデータ読み込みエラー ({file_name}): {e}")
                # file_info['band'] = st.text_input(f"{file_name} の色分け用バンド", value=file_info["band"], key=f"band_upload_{file_name}")

            # file_infoを追加
            if not any(entry['name'] == file_info['name'] for entry in st.session_state["upload_entries"]):
                st.session_state["upload_entries"].append(file_info)

        # プレビューとカラムの設定
        for i, file_info in enumerate(st.session_state["upload_entries"]):
            if file_info["loaded"]:
                file_name = file_info["name"]
                ext = os.path.splitext(file_name)[1].lower()
                st.write(f"**{file_name} プレビュー:**")
                preview_data = file_info["preview"]
                if isinstance(preview_data, pd.DataFrame):
                    st.dataframe(preview_data.head())
                elif isinstance(preview_data, gpd.GeoDataFrame):
                    st.dataframe(preview_data.head())
                else:
                    st.json(preview_data)
                # CSVの場合は緯度経度カラム、TIFFの場合はバンドなどを入力
                if ext == ".csv":
                    lat_col_key = f"lat_column_{file_name}"
                    lon_col_key = f"lon_column_{file_name}"
                    lat_default = st.session_state.get(f"lat_column_{file_name}", "lat")
                    lon_default = st.session_state.get(f"lon_column_{file_name}", "lon")
                    st.session_state["upload_entries"][i]["lat_col"] = st.text_input(
                        f"{file_name} の緯度カラム", value=lat_default, key=lat_col_key
                    )
                    st.success(f"{file_name} の緯度カラムを{lat_default} に設定しました。")
                    st.session_state["upload_entries"][i]["lon_col"] = st.text_input(
                        f"{file_name} の経度カラム", value=lon_default, key=lon_col_key
                    )
                    st.success(f"{file_name} の経度カラムを{lon_default} に設定しました。")
                elif ext in [".tiff", ".tif"]:
                    band_key = f"band_upload_{file_name}"
                    band_default = st.session_state.get(f"band_upload_{file_name}", 1)
                    st.session_state["upload_entries"][i]["band"] = st.text_input(
                        f"{file_name} の色分け用バンド", value=band_default, key=band_key
                    )
                    st.success(f"{file_name} の色分け用バンドを{band_default} に設定しました。")

    # 選択されたファイルの一覧
    st.write("### 選択されたファイル一覧:")
    # print(st.session_state)
    if "folder_entries" in st.session_state and st.session_state["folder_entries"]: # Inputフォルダからのファイル情報
        st.write("#### Inputフォルダ:")
        for file_info in st.session_state["folder_entries"]:
            st.write(f"{file_info.get('name', 'error:name')} ({file_info.get('source', 'error:source')})")
            st.write(f"file_info: {file_info}")
    if "url_entries" in st.session_state and st.session_state["url_entries"]: # URL入力によるファイル情報
        st.write("#### URL入力:")
        for file_info in st.session_state["url_entries"]:
            st.write(f"{file_info.get('url', 'error:url')} ({file_info.get('source', 'error:source')})")
            st.write(f"file_info: {file_info}")
    if "upload_entries" in st.session_state and st.session_state["upload_entries"]:  #アップロードによるファイル情報
        st.write("#### アップロード:")
        for file_info in st.session_state["upload_entries"]:
            st.write(f"{file_info.get('name', 'error:name')} ({file_info.get('source', 'error:source')})")
            st.write(f"file_info: {file_info}")

def display_dashboard():
    st.header("ダッシュボード表示画面")
    st.write("以下の地図上に、選択されたデータを表示します。")
    
    # foliumで地図を初期化（例：日本付近を中心に表示）
    m = folium.Map(location=[36, 138], zoom_start=5)
    
    # 1. Inputフォルダからのファイル情報 (st.session_state["folder_entries"])
    if "folder_entries" in st.session_state:
        for file_info in st.session_state["folder_entries"]:
            name = file_info["name"]
            ext = os.path.splitext(name)[1].lower()
            if file_info.get("source") == "folder":
                if ext == ".csv":
                    try:
                        df = file_info["preview"]
                        lat_col = file_info.get("lat_col", "lat")
                        print(f"lat_col: {lat_col}")
                        lon_col = file_info.get("lon_col", "lon")
                        print(f"lon_col: {lon_col}")
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
                        gdf = gpd.read_file(file_info["path"])
                        folium.GeoJson(gdf).add_to(m)
                    except Exception as e:
                        st.error(f"GeoJSONファイル {name} の読み込みエラー: {e}")
                elif ext in [".tiff", ".tif"]:
                    st.info(f"TIFFファイル {name} の地図上へのオーバーレイは現状実装されていません。")

    # 2. URL入力によるファイル情報 (st.session_state["url_entries"])
    if "url_entries" in st.session_state:
        for file_info in st.session_state["url_entries"]:
            # name があればそれを、なければ URL を使用
            name = file_info.get("name", file_info.get("url", ""))
            ext = os.path.splitext(name)[1].lower()
            if file_info.get("source", "") == "url":
                if ext == ".csv":
                    try:
                        df = file_info["preview"]
                        lat_col = file_info.get("lat_col", "lat")
                        print(f"lat_col: {lat_col}")
                        lon_col = file_info.get("lon_col", "lon")
                        print(f"lon_col: {lon_col}")
                        if lat_col in df.columns and lon_col in df.columns:
                            for idx, row in df.iterrows():
                                folium.Marker(
                                    location=[row[lat_col], row[lon_col]],
                                    popup=f"{name}: {row.to_dict()}"
                                ).add_to(m)
                        else:
                            st.warning(f"CSVファイル {name} に指定された緯度カラム '{lat_col}' と経度カラム '{lon_col}' が見つかりません。")
                    except Exception as e:
                        st.error(f"CSV URL {file_info['url']} の読み込みエラー: {e}")
                elif ext == ".geojson":
                    try:
                        gdf = gpd.read_file(file_info["url"])
                        folium.GeoJson(gdf).add_to(m)
                    except Exception as e:
                        st.error(f"GeoJSON URL {file_info['url']} の読み込みエラー: {e}")
                elif ext in [".tiff", ".tif"]:
                    st.info(f"TIFFファイル {name} の地図上へのオーバーレイは現状実装されていません。")
    
    # 3. アップロードされたファイル情報 (st.session_state["upload_entries"])
    if "upload_entries" in st.session_state:
        for file_info in st.session_state["upload_entries"]:
            name = file_info["name"]
            ext = os.path.splitext(name)[1].lower()
            if file_info.get("source") == "upload":
                if ext == ".csv":
                    try:
                        df = file_info["preview"]
                        lat_col = file_info.get("lat_col", "lat")
                        print(f"lat_col: {lat_col}")
                        lon_col = file_info.get("lon_col", "lon")
                        print(f"lon_col: {lon_col}")
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
                        file_info["file"].seek(0)
                        gdf = gpd.read_file(file_info["file"])
                        folium.GeoJson(gdf).add_to(m)
                    except Exception as e:
                        st.error(f"アップロードGeoJSONファイル {name} の読み込みエラー: {e}")
                elif ext in [".tiff", ".tif"]:
                    st.info(f"アップロードされたTIFFファイル {name} の地図上へのオーバーレイは現状実装されていません。")
    
    st_folium(m)

def display_dashboard_plotly():
    st.header("ダッシュボード表示画面")
    st.write("以下の地図上に、選択されたデータを表示します。")

    # Plotly用の地図フィギュアを作成（初期設定：open-street-map、中心は日本付近）
    fig = go.Figure()
    fig.update_layout(
        mapbox_style="open-street-map",
        mapbox=dict(center=dict(lat=36, lon=138), zoom=5),
        margin={"r":0, "t":0, "l":0, "b":0}
    )

    # 1. Inputフォルダからのファイル情報 (st.session_state["folder_entries"])
    if "folder_entries" in st.session_state:
        for file_info in st.session_state["folder_entries"]:
            name = file_info["name"]
            ext = os.path.splitext(name)[1].lower()
            if file_info.get("source") == "folder":
                if ext == ".csv":
                    try:
                        # キャッシュされたプレビューを利用
                        df = file_info.get("preview", pd.read_csv(file_info["path"]))
                        lat_col = file_info.get("lat_col", "lat")
                        lon_col = file_info.get("lon_col", "lon")
                        if lat_col in df.columns and lon_col in df.columns:
                            scatter = px.scatter_mapbox(
                                df,
                                lat=lat_col,
                                lon=lon_col,
                                hover_data=df.columns,
                                zoom=5
                            )
                            for trace in scatter.data:
                                fig.add_trace(trace)
                        else:
                            st.warning(f"CSVファイル {name} に指定された緯度カラム '{lat_col}' と経度カラム '{lon_col}' が見つかりません。")
                    except Exception as e:
                        st.error(f"CSVファイル {name} の読み込みエラー: {e}")
                elif ext == ".geojson":
                    try:
                        # GeoPandasで読み込み→GeoJSON形式に変換
                        gdf = gpd.read_file(file_info["path"])
                        geojson = gdf.__geo_interface__
                        # 色付けのためのダミー列を作成
                        if "dummy" not in gdf.columns:
                            gdf["dummy"] = 1
                        choropleth = px.choropleth_mapbox(
                            gdf,
                            geojson=geojson,
                            locations=gdf.index,
                            color="dummy",
                            center={"lat": 36, "lon": 138},
                            mapbox_style="open-street-map",
                            zoom=5,
                            opacity=0.5
                        )
                        for trace in choropleth.data:
                            fig.add_trace(trace)
                    except Exception as e:
                        st.error(f"GeoJSONファイル {name} の読み込みエラー: {e}")
                elif ext in [".tiff", ".tif"]:
                    st.info(f"TIFFファイル {name} の表示は現状実装されていません。")

    # 2. URL入力によるファイル情報 (st.session_state["url_entries"])
    if "url_entries" in st.session_state:
        for file_info in st.session_state["url_entries"]:
            name = file_info.get("name", file_info.get("url", ""))
            ext = os.path.splitext(name)[1].lower()
            if file_info.get("source", "url") == "url":
                if ext == ".csv":
                    try:
                        df = file_info.get("preview", pd.read_csv(file_info["url"]))
                        lat_col = file_info.get("lat_col", "lat")
                        lon_col = file_info.get("lon_col", "lon")
                        if lat_col in df.columns and lon_col in df.columns:
                            scatter = px.scatter_mapbox(
                                df,
                                lat=lat_col,
                                lon=lon_col,
                                hover_data=df.columns,
                                zoom=5
                            )
                            for trace in scatter.data:
                                fig.add_trace(trace)
                        else:
                            st.warning(f"CSVファイル {name} に指定された緯度カラム '{lat_col}' と経度カラム '{lon_col}' が見つかりません。")
                    except Exception as e:
                        st.error(f"CSV URL {file_info['url']} の読み込みエラー: {e}")
                elif ext == ".geojson":
                    try:
                        gdf = gpd.read_file(file_info["url"])
                        geojson = gdf.__geo_interface__
                        if "dummy" not in gdf.columns:
                            gdf["dummy"] = 1
                        choropleth = px.choropleth_mapbox(
                            gdf,
                            geojson=geojson,
                            locations=gdf.index,
                            color="dummy",
                            center={"lat": 36, "lon": 138},
                            mapbox_style="open-street-map",
                            zoom=5,
                            opacity=0.5
                        )
                        for trace in choropleth.data:
                            fig.add_trace(trace)
                    except Exception as e:
                        st.error(f"GeoJSON URL {file_info['url']} の読み込みエラー: {e}")
                elif ext in [".tiff", ".tif"]:
                    st.info(f"TIFFファイル {name} の表示は現状実装されていません。")
    
    # 3. アップロードによるファイル情報 (st.session_state["upload_entries"])
    if "upload_entries" in st.session_state:
        for file_info in st.session_state["upload_entries"]:
            name = file_info["name"]
            ext = os.path.splitext(name)[1].lower()
            if file_info.get("source") == "upload":
                if ext == ".csv":
                    try:
                        df = file_info.get("preview", pd.read_csv(file_info["file"]))
                        lat_col = file_info.get("lat_col", "lat")
                        lon_col = file_info.get("lon_col", "lon")
                        if lat_col in df.columns and lon_col in df.columns:
                            scatter = px.scatter_mapbox(
                                df,
                                lat=lat_col,
                                lon=lon_col,
                                hover_data=df.columns,
                                zoom=5
                            )
                            for trace in scatter.data:
                                fig.add_trace(trace)
                        else:
                            st.warning(f"CSVファイル {name} に指定された緯度カラム '{lat_col}' と経度カラム '{lon_col}' が見つかりません。")
                    except Exception as e:
                        st.error(f"アップロードCSVファイル {name} の読み込みエラー: {e}")
                elif ext == ".geojson":
                    try:
                        file_info["file"].seek(0)
                        gdf = gpd.read_file(file_info["file"])
                        geojson = gdf.__geo_interface__
                        if "dummy" not in gdf.columns:
                            gdf["dummy"] = 1
                        choropleth = px.choropleth_mapbox(
                            gdf,
                            geojson=geojson,
                            locations=gdf.index,
                            color="dummy",
                            center={"lat": 36, "lon": 138},
                            mapbox_style="open-street-map",
                            zoom=5,
                            opacity=0.5
                        )
                        for trace in choropleth.data:
                            fig.add_trace(trace)
                    except Exception as e:
                        st.error(f"アップロードGeoJSONファイル {name} の読み込みエラー: {e}")
                elif ext in [".tiff", ".tif"]:
                    st.info(f"アップロードされたTIFFファイル {name} の表示は現状実装されていません。")
    
    st.plotly_chart(fig, use_container_width=True)

def display_dashboard_plotly_pydeck():
    st.header("ダッシュボード表示画面")
    
    # すべてのエントリを統合
    all_entries = []
    if "folder_entries" in st.session_state:
        all_entries.extend(st.session_state["folder_entries"])
    if "url_entries" in st.session_state:
        all_entries.extend(st.session_state["url_entries"])
    if "upload_entries" in st.session_state:
        all_entries.extend(st.session_state["upload_entries"])

    st.sidebar.header("条件設定")
    st.sidebar.write("all_entries:")
    st.sidebar.write(all_entries)
    
    # --- Pydeck 用：大容量地理空間ファイルの表示 ---
    map_layers = []
    all_lat = []
    all_lon = []
    # CSV・GeoJSON で、緯度・経度の情報が存在するものを対象とする
    for file_info in all_entries:
        file_name = file_info.get("name", "")
        ext = os.path.splitext(file_name)[1].lower()
        # CSVの場合：プレビューは file_info["preview"]（サンプリング済みであることを想定）
        if ext == ".csv":
            try:
                df = file_info.get("preview", None)
                st.sidebar.write(f"file_name: {file_info.get('name', None)}")
                lat_col = file_info.get("lat_col", "lat")
                lon_col = file_info.get("lon_col", "lon")
                st.sidebar.write(f"lat_col: {lat_col} lon_col: {lon_col}")
                if df is not None:
                    st.sidebar.write(df.describe())
                    # 大きなデータの場合はサンプルを抽出（例：50,000行）
                    if len(df) > 110000:
                        df_sample = df.sample(n=110000, random_state=42)
                        st.sidebar.warning(f"{file_name}を110000行にサンプル済み")
                    else:
                        df_sample = df
                if lat_col in df_sample.columns and lon_col in df_sample.columns:
                    all_lat.extend(df_sample[lat_col].dropna().tolist())
                    all_lon.extend(df_sample[lon_col].dropna().tolist())
                    # 属性カラムによる色分け
                    columns_list = df_sample.columns
                    color_attr = st.sidebar.selectbox("Inputフォルダ内のファイル", columns_list)
                    if color_attr and color_attr in df_sample.columns:
                        # プルダウンでカラーマップを選択
                        cmap_choice = st.sidebar.selectbox(
                            "カラーマップを選択",
                            ["terrain", "Reds", "Blues", "Greens", "cividis", "magma", "viridis", "twilight", "cool", "coolwarm", "spring", "summer", "autumn", "winter"],
                            key=f"cmap_{file_info.get('name')}"
                        )
                        cmap = cm.get_cmap(cmap_choice)
                        unique_vals = df_sample[color_attr].unique()
                        if np.issubdtype(unique_vals.dtype, np.number):
                            norm = mcolors.Normalize(vmin=unique_vals.min(), vmax=unique_vals.max())
                            df_sample["get_color"] = df_sample[color_attr].apply(
                                lambda x: [int(c*255) for c in cmap(norm(x))[:3]] + [160]
                            )
                        else:
                            categories = sorted(unique_vals)
                            n = len(categories)
                            mapping = {cat: cmap(i/(n-1) if n>1 else 0.5) for i, cat in enumerate(categories)}
                            df_sample["get_color"] = df_sample[color_attr].apply(
                                lambda x: [int(c*255) for c in mapping[x][:3]] + [160]
                            )
                        get_color_expr = "get_color"
                    else:
                        get_color_expr = [200,30,0,160]
                    # サイズ
                    radius = st.sidebar.text_input(f"半径", value=30, key="radius_key")
                    layer = pdk.Layer(
                        "ScatterplotLayer",
                        data=df_sample,
                        get_position=[lon_col, lat_col],
                        get_fill_color=get_color_expr,
                        get_radius=radius,
                    )
                    map_layers.append(layer)
                else:
                    st.sidebar.warning(f"CSVファイル {file_name} に指定された緯度/経度カラムが見つかりません。")
            except Exception as e:
                st.sidebar.error(f"CSVファイル {file_name} のマップレイヤー生成エラー: {e}")
        # GeoJSONの場合
        elif ext == ".geojson":
            try:
                gdf = file_info.get("preview", None)
                if gdf is not None:
                    st.sidebar.write(gdf.describe())
                    if len(gdf) > 50000:
                        gdf_sample = gdf.sample(n=50000, random_state=42)
                        st.sidebar.warning(f"{file_name}を50000行にサンプル済み")
                    else:
                        gdf_sample = gdf
                    # 属性カラムによる色分け
                    columns_list = gdf_sample.columns
                    color_attr = st.sidebar.selectbox("Inputフォルダ内のファイル", columns_list)
                    if color_attr and color_attr in gdf_sample.columns:
                        # プルダウンでカラーマップを選択
                        cmap_choice = st.sidebar.selectbox(
                            "カラーマップを選択",
                            ["terrain", "Reds", "Blues", "Greens", "cividis", "magma", "viridis", "twilight", "cool", "coolwarm", "spring", "summer", "autumn", "winter"],
                            key=f"cmap_{file_info.get('name')}"
                        )
                        cmap = cm.get_cmap(cmap_choice)
                        unique_vals = gdf_sample[color_attr].unique()
                        if np.issubdtype(unique_vals.dtype, np.number):
                            norm = mcolors.Normalize(vmin=unique_vals.min(), vmax=unique_vals.max())
                            # 各フィーチャーに対して、色を計算し、properties に "get_color" として保存
                            for feature in geojson_data["features"]:
                                if color_attr in feature["properties"]:
                                    val = feature["properties"][color_attr]
                                    color = cmap(norm(val))  # RGBA (0～1)
                                    # 0～255 に変換し、alpha を固定(例: 160)
                                    feature["properties"]["get_color"] = [int(255 * color[i]) for i in range(3)] + [160]
                                else:
                                    # "value" がなければデフォルト色を設定
                                    feature["properties"]["get_color"] = [200, 30, 0, 160]
                    # サイズ
                    radius = st.sidebar.text_input(f"半径", value=30, key="radius_key")
                    # 座標の中心は gdf の全体境界から計算
                    bounds = gdf_sample.total_bounds  # [minx, miny, maxx, maxy]
                    center_lat = (bounds[1] + bounds[3]) / 2
                    center_lon = (bounds[0] + bounds[2]) / 2
                    all_lat.append(center_lat)
                    all_lon.append(center_lon)
                    geojson_data = gdf_sample.__geo_interface__
                    all_lat.extend(df_sample[lat_col].dropna().tolist())
                    all_lon.extend(df_sample[lon_col].dropna().tolist())
                    geojson_layer = pdk.Layer(
                        "GeoJsonLayer",
                        data=geojson_data,
                        get_fill_color="properties.get_color",
                        pickable=True,
                        auto_highlight=True,
                        stroked=True,
                        get_radius=radius,
                    )
                    map_layers.append(layer)
                else:
                    st.sidebar.warning(f"GeoJSONファイル {file_name} の読み込みに失敗しました。")
            except Exception as e:
                st.sidebar.error(f"GeoJSONファイル {file_name} のマップレイヤー生成エラー: {e}")
        elif ext in [".tiff", ".tif"]:
            st.sidebar.info(f"TIFFファイル {file_name} はマップ表示対象外です。")
    
    # 自動で中心とズームレベルを設定
    if all_lat and all_lon:
        center_lat = sum(all_lat) / len(all_lat)
        center_lon = sum(all_lon) / len(all_lon)
        lat_extent = max(all_lat) - min(all_lat)
        lon_extent = max(all_lon) - min(all_lon)
        extent = max(lat_extent, lon_extent)
        if extent < 0.1:
            zoom_level = 15
        elif extent < 1:
            zoom_level = 10
        else:
            zoom_level = 5
    else:
        center_lat, center_lon, zoom_level = 36, 138, 5

    if map_layers:
        deck_chart = pdk.Deck(
            initial_view_state=pdk.ViewState(
                latitude=center_lat,
                longitude=center_lon,
                zoom=zoom_level,
            ),
            layers=map_layers,
            map_style="mapbox://styles/mapbox/light-v9",
        )
    else:
        deck_chart = None

    # --- Plotly 用：複数ファイルのグラフ作成 ---
    # ここでは例として、各CSVファイルに "x" と "y" 列があると仮定し、散布図を作成
    combined_df_list = []
    for file_info in all_entries:
        ext = os.path.splitext(file_info.get("name", ""))[1].lower()
        if ext == ".csv":
            try:
                df = file_info.get("preview", None)
                if df is not None and "x" in df.columns and "y" in df.columns:
                    df_temp = df.copy()
                    df_temp["source_file"] = file_info.get("name", "unknown")
                    combined_df_list.append(df_temp)
            except Exception as e:
                st.error(f"CSVファイル {file_info.get('name')} のグラフ用データ読み込みエラー: {e}")
    if combined_df_list:
        combined_df = pd.concat(combined_df_list)
        plotly_fig = px.scatter(
            combined_df,
            x="x",
            y="y",
            color="source_file",
            title="複数ファイルの散布図"
        )
    else:
        plotly_fig = None

    # --- 上下レイアウトで表示 ---
    top_container = st.container()
    bottom_container = st.container()
    
    with top_container:
        st.subheader("地図表示")
        if deck_chart is not None:
            st.pydeck_chart(deck_chart, use_container_width=True)
        else:
            st.info("表示する地図レイヤーがありません。")
    
    with bottom_container:
        st.subheader("グラフ")
        if plotly_fig is not None:
            st.plotly_chart(plotly_fig, use_container_width=True)
        else:
            st.info("表示するグラフデータがありません。")

def main():
    st.title("データ表示ダッシュボードアプリ")
    
    tab1, tab2 = st.tabs(["ファイル選択", "ダッシュボード表示"])
    
    with tab1:
        file_selection_screen()
    
    with tab2:
        try:
            display_dashboard_plotly_pydeck()
        except Exception as e:
            st.warning(f"Error: {e}")

if __name__ == "__main__":
    main()