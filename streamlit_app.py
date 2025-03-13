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
import base64
from io import BytesIO
from PIL import Image
import pyarrow as pa

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
                    file_info["preview"] = load_tiff_preview_as_array(file_info["path"])
                    file_info["loaded"] = True
                except Exception as e:
                    st.error(f"TIFFメタデータ読み込みエラー ({file_name}): {e}")

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
        if url_input in [ent["url"] for ent in st.session_state["url_entries"][:i]]:
            st.error("同じURLが既に入力されています。")
            continue

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
                                    bounds = src.bounds  # left, bottom, right, top
                                    image_data = src.read()  # shape: (bands, height, width)
                                    gray = image_data[0]
                                    preview = {"img_array": gray, "bounds": [[bounds.left, bounds.bottom], [bounds.right, bounds.top]]}
                            st.success(f"{file_name} の読み込みが完了しました。")
                            st.session_state["url_entries"][i]["preview"] = preview
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
        # すでに別のURL欄が追加済みでなければ追加（例：連続再実行で2つ以上増えないようにチェックする）
        # 下のように単純に追加すると、読み込むたび無限に増えるので「まだ空のURL欄を持つエントリが存在しない場合のみ追加」などのチェックを入れる
        empty_urls = [
            ent for ent in st.session_state["url_entries"] 
            if ent["url"] == "" and not ent["loaded"]
        ]
        if not empty_urls and st.button("URL入力欄追加", key=f"add_url_input_{last_index}"):
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
            st.rerun()

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
                    file_info["preview"] = load_tiff_preview_as_array(uploaded_file)
                    file_info["loaded"] = True
                except Exception as e:
                    st.error(f"TIFFメタデータ読み込みエラー ({file_name}): {e}")

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

def load_tiff_preview_as_array(file_path): # 単一バンドのみに対応
    with rasterio.open(file_path) as src:
        bounds = src.bounds  # left, bottom, right, top
        image_data = src.read()  # shape: (bands, height, width)
        gray = image_data[0]
    return {"img_array": gray, "bounds": [[bounds.left, bounds.bottom], [bounds.right, bounds.top]]}

def numpy_array_to_data_uri(img_array):
    img = Image.fromarray(img_array)
    buffer = BytesIO()
    img.save(buffer, format="PNG")
    encoded = base64.b64encode(buffer.getvalue()).decode("utf-8")
    return f"data:image/png;base64,{encoded}"

def display_dashboard():
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

    # レイヤーパネル
    st.sidebar.header("レイヤーパネル")
    layer_visibility = {}
    for file_info in all_entries:
        if file_info.get("source", "") == "url":
            if file_info.get("loaded", True) is False:
                continue
        file_name = file_info.get("name", "")
        layer_visibility[file_name] = st.sidebar.checkbox(f"{file_name} を表示", value=True)

    # --- Pydeck 用：大容量地理空間ファイルの表示 ---
    map_layers = []
    all_lat = []
    all_lon = []
    # CSV・GeoJSON で、緯度・経度の情報が存在するものを対象とする
    for file_info in all_entries:
        fname = file_info.get("name", "")
        # レイヤーパネルで非表示になっている場合はスキップ
        if fname and not layer_visibility.get(fname, True):
            continue
        file_name = fname
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
                    # 大きなデータの場合はサンプルを抽出
                    # if len(df) > 110000:
                        # df_sample = df.sample(n=110000, random_state=42)
                        # st.sidebar.warning(f"{file_name}を110000行にサンプル済み")
                    # else:
                    df_sample = df
                if lat_col in df_sample.columns and lon_col in df_sample.columns:
                    all_lat.extend(df_sample[lat_col].dropna().tolist())
                    all_lon.extend(df_sample[lon_col].dropna().tolist())
                    # 属性カラムによる色分け
                    columns_list = df_sample.columns.tolist()
                    columns_list.extend([None])
                    color_attr = st.sidebar.selectbox(f"Inputフォルダ内のファイル{file_name}", columns_list, format_func=lambda x: "None" if x is None else x)
                    if color_attr and color_attr in df_sample.columns:
                        # プルダウンでカラーマップを選択
                        cmap_choice = st.sidebar.selectbox(
                            "カラーマップを選択",
                            ["terrain", "Reds", "Blues", "Greens", "cividis", "magma", "viridis", "twilight", "cool", "coolwarm", "spring", "summer", "autumn", "winter"],
                            key=f"cmap_{file_info.get('name')}"
                        )
                        cmap = plt.get_cmap(cmap_choice)
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
                    radius = st.sidebar.text_input(f"半径", value=30, key=f"radius_key_{file_name}")
                    # アイコンで表示かポイントで表示かを選択
                    # if st.sidebar.checkbox("アイコンで表示", value=False):
                    #     # アイコンのアトラス（1枚の画像に複数のアイコンが含まれる画像）と、アイコンのマッピング情報を設定
                    #     icon_atlas = "./resource/icon-atlas.png"
                    #     icon_mapping = {
                    #         "marker": {"x": 0, "y": 0, "width": 128, "height": 128, "mask": True},
                    #     }
                    #     icon_layer = pdk.Layer(
                    #         "IconLayer",
                    #         data=df_sample,
                    #         get_icon="icon",
                    #         get_position=[lon_col, lat_col],
                    #         sizeScale=15,
                    #         iconAtlas=icon_atlas,
                    #         iconMapping=icon_mapping,
                    #     )
                    #     map_layers.append(icon_layer)
                    # else:
                    csv_layer = pdk.Layer(
                        "ScatterplotLayer",
                        data=df_sample,
                        get_position=[lon_col, lat_col],
                        get_fill_color=get_color_expr,
                        get_radius=radius,
                        pickable=True,
                        auto_highlight=True,
                    )
                    map_layers.append(csv_layer)
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
                    # 大きなデータの場合はサンプルを抽出
                    # if len(gdf) > 50000:
                    #     gdf_sample = gdf.sample(n=50000, random_state=42)
                    #     st.sidebar.warning(f"{file_name}を50000行にサンプル済み")
                    # else:
                    gdf_sample = gdf
                    geojson_data = gdf_sample.__geo_interface__
                    # 属性カラムによる色分け
                    columns_list = gdf_sample.columns.tolist()
                    columns_list.extend([None])
                    color_attr = st.sidebar.selectbox(f"Inputフォルダ内のファイル{file_name}", columns_list, format_func=lambda x: "None" if x is None else x)
                    if color_attr and color_attr in gdf_sample.columns:
                        # プルダウンでカラーマップを選択
                        cmap_choice = st.sidebar.selectbox(
                            "カラーマップを選択",
                            ["terrain", "Reds", "Blues", "Greens", "cividis", "magma", "viridis", "twilight", "cool", "coolwarm", "spring", "summer", "autumn", "winter"],
                            key=f"cmap_{file_info.get('name')}"
                        )
                        cmap = plt.get_cmap(cmap_choice)
                        unique_vals = gdf_sample[color_attr].dropna().unique()  # nullは除外
                        if np.issubdtype(unique_vals.dtype, np.number):
                            norm = mcolors.Normalize(vmin=unique_vals.min(), vmax=unique_vals.max())
                            # 各フィーチャーに対して、色を計算し、properties に "get_color" として保存
                            for feature in geojson_data["features"]:
                                if color_attr in feature["properties"]:
                                    val = feature["properties"][color_attr]
                                    if val is None:
                                        feature["properties"]["get_color"] = [200, 30, 0, 160]
                                        continue
                                    color = cmap(norm(val))  # RGBA (0～1)
                                    # 0～255 に変換し、alpha を固定(例: 160)
                                    feature["properties"]["get_color"] = [int(255 * color[i]) for i in range(3)] + [160]
                                else:
                                    # color_attr がなければデフォルト色を設定
                                    feature["properties"]["get_color"] = [200, 30, 0, 160]
                        else:
                            # 数値型でない場合は全てにデフォルト色を設定
                            for feature in geojson_data["features"]:
                                feature["properties"]["get_color"] = [200, 30, 0, 160]
                    # 座標の中心は gdf の全体境界から計算
                    bounds = gdf_sample.total_bounds  # [minx, miny, maxx, maxy]
                    center_lat = (bounds[1] + bounds[3]) / 2
                    center_lon = (bounds[0] + bounds[2]) / 2
                    all_lat.append(center_lat)
                    all_lon.append(center_lon)
                    # ジオメトリの種類によって処理を分ける
                    if gdf_sample.geometry.geom_type.iloc[0] == "Point":
                    #     if st.button("アイコンで表示", key=f"icon_button_{file_name}"):
                    #         # アイコンのアトラス（1枚の画像に複数のアイコンが含まれる画像）と、アイコンのマッピング情報を設定
                    #         icon_atlas = "./resource/icon-atlas.png"
                    #         icon_mapping = {
                    #             "marker": {"x": 0, "y": 0, "width": 128, "height": 128, "mask": True},
                    #         }

                    #         icon_layer = pdk.Layer(
                    #             "IconLayer",
                    #             data=gdf_sample,
                    #             get_icon="icon",
                    #             get_position="geometry.coordinates",
                    #             sizeScale=15,
                    #             iconAtlas=icon_atlas,
                    #             iconMapping=icon_mapping,
                    #         )
                    #         map_layers.append(icon_layer)
                    #     elif st.button("ポイントで表示", key=f"point_button_{file_name}"):
                        # CSVの場合にはポイントのサイズ
                        radius = st.sidebar.text_input(f"半径", value=30, key=f"radius_key_{file_name}")
                        # Pointの場合にはScatterplotLayer
                        geojson_layer = pdk.Layer(
                            "ScatterplotLayer",
                            data=gdf_sample,
                            get_position="geometry.coordinates",
                            get_fill_color="properties.get_color",
                            get_radius=radius,
                            pickable=True,
                            auto_highlight=True,
                        )
                        map_layers.append(geojson_layer)
                    else:
                        geojson_layer = pdk.Layer(
                            "GeoJsonLayer",
                            data=geojson_data,
                            get_fill_color="properties.get_color",
                            pickable=True,
                            auto_highlight=True,
                        )
                        map_layers.append(geojson_layer)
                else:
                    st.sidebar.warning(f"GeoJSONファイル {file_name} の読み込みに失敗しました。")
            except Exception as e:
                st.sidebar.error(f"GeoJSONファイル {file_name} のマップレイヤー生成エラー: {e}")
        # TIFFの場合
        elif ext in [".tiff", ".tif"]:
            try:
                preview = file_info.get("preview", None)
                if preview is not None:
                    img_array = preview.get("img_array", None)
                    bounds = preview.get("bounds", None)
                    if img_array is not None:
                        img_url = numpy_array_to_data_uri(img_array)
                        img_url_ = f'{img_url}'
                    if bounds is not None:
                        bounds_left = bounds[0][0]
                        bounds_bottom = bounds[0][1]
                        bounds_right = bounds[1][0]
                        bounds_top = bounds[1][1]
                # st.write(f"{img_url_}") # debug
                # BitmapLayerを作成
                # bitmap_layer = pdk.Layer(
                #     "BitmapLayer",
                #     data=None,
                #     image=img_url_,
                #     bounds=[[bounds_left, bounds_bottom], [bounds_right, bounds_top]]
                # )
                # map_layers.append(bitmap_layer)
                # st.write(f"TIFFファイル {file_name} をマップレイヤーに追加しました。")
                st.sidebar.warning(f"TIFFファイル {file_name} には対応していません。")
            except Exception as e:
                st.sidebar.error(f"TIFFファイル {file_name} の読み込みエラー: {e}")

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
    if "all_entries" not in st.session_state or len(st.session_state["all_entries"]) == 0:
        st.error("表示するファイルがありません。")
    else:
        # 1. 対象ファイルの選択
        file_options = [fi["name"] for fi in st.session_state["all_entries"] if "name" in fi]
        file_choice = st.selectbox("ファイルを選択", options=file_options)
        # 選択された file_info を取得
        file_info = next(fi for fi in st.session_state["all_entries"] if fi.get("name") == file_choice)
        df = file_info.get("preview")
        if df is None:
            st.error("選択されたファイルのプレビューがありません。")
        elif isinstance(df, pd.DataFrame) or isinstance(df, gpd.GeoDataFrame):
            # Plotly 用グラフ用変数を初期化
            plotly_fig = None
            # 2. 2つのカラムの選択（df.columns から）
            cols = df.columns.tolist()
            col1 = st.selectbox("1つ目のカラムを選択", options=cols, key="plot_col1")
            col2 = st.selectbox("2つ目のカラムを選択", options=cols, key="plot_col2")
            
            # 3. グラフの種類の選択
            graph_type = st.selectbox("グラフの種類を選択", options=["散布図", "クロス集計の積み上げ棒グラフ（縦）", "各カラムの円グラフ"])
            
            # 4. カテゴリ数が多い場合のグループ化処理
            def group_categories(series, max_categories=5):
                counts = series.value_counts()
                if len(counts) > max_categories:
                    top_categories = counts.index[:max_categories]
                    return series.apply(lambda x: x if x in top_categories else "Other")
                return series
            
            # 5. グラフ作成
            if graph_type == "散布図":
                try:
                    df_numeric = df[[col1, col2]].apply(pd.to_numeric, errors="coerce")
                    plotly_fig = px.scatter(df_numeric, x=col1, y=col2, title="散布図")
                except Exception as e:
                    st.error(f"散布図作成エラー: {e}")
            elif graph_type == "クロス集計の積み上げ棒グラフ（縦）":
                try:
                    series1 = group_categories(df[col1], max_categories=5)
                    series2 = group_categories(df[col2], max_categories=5)
                    ctab = pd.crosstab(series1, series2)
                    fig = go.Figure()
                    for cat in ctab.columns:
                        fig.add_trace(go.Bar(
                            x=ctab.index,
                            y=ctab[cat],
                            name=str(cat)
                        ))
                    fig.update_layout(barmode='stack', title="クロス集計の積み上げ棒グラフ（縦）")
                    plotly_fig = fig
                except Exception as e:
                    st.error(f"積み上げ棒グラフ作成エラー: {e}")
            elif graph_type == "各カラムの円グラフ":
                try:
                    plotly_fig1 = px.pie(df, names=group_categories(df[col1], max_categories=5), title=f"{col1} の分布")
                    plotly_fig2 = px.pie(df, names=group_categories(df[col2], max_categories=5), title=f"{col2} の分布")
                except Exception as e:
                    st.error(f"円グラフ作成エラー: {e}")
        else:
            st.error("選択されたファイルは適切な形式ではありません。")

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
        elif plotly_fig1 is not None and plotly_fig2 is not None:
            st.plotly_chart(plotly_fig1, use_container_width=True)
            st.plotly_chart(plotly_fig2, use_container_width=True)
        else:
            st.info("表示するグラフデータがありません。")

def main():
    st.title("データ表示ダッシュボードアプリ")
    
    tab1, tab2 = st.tabs(["ファイル選択", "ダッシュボード表示"])
    
    with tab1:
        file_selection_screen()
    
    with tab2:
        try:
            display_dashboard()
        except Exception as e:
            st.warning(f"Error: {e}")

if __name__ == "__main__":
    main()