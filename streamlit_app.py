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
from sklearn.cluster import KMeans

st.set_page_config(layout="wide")
st.image("header.png", use_container_width=True)

def file_selection_screen():
    # 全体の再読み込みボタン
    if st.button("ページのリロード"):
        st.rerun()

    # 1. Inputフォルダからの選択
    # セッション変数 "folder_entries" の初期化（もし存在しなければ）
    if "folder_entries" not in st.session_state:
        st.session_state["folder_entries"] = []

    st.subheader("1. Inputフォルダからファイルを選択")
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
    st.subheader("2. URLからファイル入力")

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
            value="" if entry["url"] == "" else "URL入力済",
        )
        # 重複チェック
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
                    # URL入力欄をマスク
                    st.rerun()

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

    st.subheader("3. ファイルをアップロードして入力")
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
    st.success("読み込み済みファイルの一覧:")
    # print(st.session_state)
    if "folder_entries" in st.session_state and st.session_state["folder_entries"]: # Inputフォルダからのファイル情報
        for file_info in st.session_state["folder_entries"]:
            st.success(f"{file_info.get('name', 'error:name')} ({file_info.get('source', 'error:source')})")
            # st.write(f"file_info: {file_info}")
    if "url_entries" in st.session_state and st.session_state["url_entries"]: # URL入力によるファイル情報
        for file_info in st.session_state["url_entries"]:
            st.success(f"{file_info.get('name', 'error:name')} ({file_info.get('source', 'error:source')})")
            # st.write(f"file_info: {file_info}")
    if "upload_entries" in st.session_state and st.session_state["upload_entries"]:  #アップロードによるファイル情報
        for file_info in st.session_state["upload_entries"]:
            st.success(f"{file_info.get('name', 'error:name')} ({file_info.get('source', 'error:source')})")
            # st.write(f"file_info: {file_info}")

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

def group_by_range(series, max_categories=8):
    # 数値データでない場合は、各値をそのまま返す
    if not pd.api.types.is_numeric_dtype(series):
        group_range_labels = series.astype(str)
        return pd.Categorical(group_range_labels), group_range_labels

    # 欠損値のあるサンプルを除外
    clean_series = series.dropna()
    if clean_series.empty:
        # clean_series が空の場合はそのまま返す
        return pd.Categorical(clean_series.astype(str)), clean_series.astype(str)

    # 1次元のデータを2次元に変換（KMeans の入力として必要）
    X = clean_series.values.reshape(-1, 1)
    
    # クラスタ数は、max_categories とユニーク値数の小さい方にする
    unique_values = np.unique(clean_series.values)
    n_clusters = min(max_categories, len(unique_values))
    
    # k-means クラスタリングの実行
    kmeans = KMeans(n_clusters=n_clusters, random_state=42)
    labels = kmeans.fit_predict(X)
    
    # 各クラスタごとに最小値・最大値の範囲を計算し、文字列として保存
    cluster_ranges = {}
    for label in np.unique(labels):
        cluster_values = clean_series[labels == label]
        cluster_min = cluster_values.min()
        cluster_max = cluster_values.max()
        cluster_ranges[label] = f"{cluster_min:.2f} ~ {cluster_max:.2f}"
    
    # 元の (dropna後の) series の各要素に対応するクラスタの範囲の文字列を生成
    group_range_labels = pd.Series([cluster_ranges[label] for label in labels], index=clean_series.index)
    
    # クラスタ中心値の昇順で並べ替え
    cluster_centers = kmeans.cluster_centers_.flatten()
    sorted_order = np.argsort(cluster_centers)
    unique_range_labels = [cluster_ranges[label] for label in sorted_order]
    grouped_series = pd.Categorical(group_range_labels, categories=unique_range_labels, ordered=True)
    
    return grouped_series, group_range_labels

def display_dashboard():
    # すべてのエントリを統合
    all_entries = []
    if "folder_entries" in st.session_state:
        all_entries.extend(st.session_state["folder_entries"])
    if "url_entries" in st.session_state:
        all_entries.extend(st.session_state["url_entries"])
    if "upload_entries" in st.session_state:
        all_entries.extend(st.session_state["upload_entries"])

    st.sidebar.header("ダッシュボードの設定")
    # st.sidebar.write("all_entries:")
    # st.sidebar.write(all_entries)

    # レイヤーパネル
    st.sidebar.subheader("表示するファイルにチェック")
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
        st.sidebar.write(f"選択されたファイル{file_name}")
        # CSVの場合：プレビューは file_info["preview"]（サンプリング済みであることを想定）
        if ext == ".csv":
            try:
                df = file_info.get("preview", None)
                lat_col = file_info.get("lat_col", "lat")
                lon_col = file_info.get("lon_col", "lon")
                # st.sidebar.write(f"lat_col: {lat_col} lon_col: {lon_col}")
                if df is not None:
                    st.sidebar.write(df.describe())
                    # 大きなデータの場合はサンプルを抽出
                    num = 130000
                    if len(df) > num:
                        df_sample = df.sample(n=num, random_state=42)
                        st.sidebar.warning(f"{file_name}を{num}行にサンプル済み")
                    else:
                        df_sample = df
                if lat_col in df_sample.columns and lon_col in df_sample.columns:
                    all_lat.extend(df_sample[lat_col].dropna().tolist())
                    all_lon.extend(df_sample[lon_col].dropna().tolist())
                    # 属性カラムによる色分け
                    columns_list = df_sample.columns.tolist() + [None]
                    color_attr = st.sidebar.selectbox(f"色分けに用いるカラム", columns_list, format_func=lambda x: "None" if x is None else x, index=len(columns_list)-1)
                    if color_attr and color_attr in df_sample.columns:
                        # プルダウンでカラーマップを選択
                        cmap_choice = st.sidebar.selectbox(
                            "カラーマップを選択",
                            ["terrain", "Reds", "Blues", "Greens", "cividis", "magma", "viridis", "twilight", "cool", "coolwarm", "spring", "summer", "autumn", "winter"],
                            key=f"cmap_{file_info.get('name')}"
                        )
                        cmap = plt.get_cmap(cmap_choice)
                        filled_vals = df_sample[color_attr].fillna(0)
                        unique_vals = filled_vals.unique()
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
                        color_choice = st.sidebar.selectbox(
                            "カラーを選択",
                            ["Red", "Green", "Blue", "Purple", "Yellow", "Orange", "Black", "White"],
                            key=f"color_{file_info.get('name')}"
                        )
                        # 選択肢に対応するRGBAの値（最後の値は透明度）
                        color_dict = {
                            "Red": [255, 0, 0, 160],
                            "Green": [0, 255, 0, 160],
                            "Blue": [0, 0, 255, 160],
                            "Purple": [128, 0, 128, 160],
                            "Yellow": [255, 255, 0, 160],
                            "Orange": [255, 165, 0, 160],
                            "Black": [0, 0, 0, 160],
                            "White": [255, 255, 255, 160]
                        }
                        get_color_expr = color_dict.get(color_choice, [200, 30, 0, 160])
                    # サイズ
                    radius = st.sidebar.text_input(f"半径", value=10, key=f"radius_key_{file_name}")
                    # アイコン表示かポイント表示かを選択
                    # if st.sidebar.checkbox("アイコンで表示", value=False, key=f"icon_button_{file_name}"):
                    #     # アイコンのアトラス（1枚の画像に複数のアイコンが含まれる画像）と、アイコンのマッピング情報を設定
                    #     icon_atlas = "./icon-atlas.png"
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
                    num = 50000
                    if len(gdf) > num:
                        gdf_sample = gdf.sample(n=num, random_state=42)
                        st.sidebar.warning(f"{file_name}を{num}行にサンプル済み")
                    else:
                        gdf_sample = gdf
                    geojson_data = gdf_sample.__geo_interface__
                    # 属性カラムによる色分け
                    columns_list = gdf_sample.columns.tolist() + [None]
                    color_attr = st.sidebar.selectbox(f"色分けに用いるカラム", columns_list, format_func=lambda x: "None" if x is None else x, index=len(columns_list)-1)
                    if color_attr and color_attr in gdf_sample.columns:
                        # プルダウンでカラーマップを選択
                        cmap_choice = st.sidebar.selectbox(
                            "カラーマップを選択",
                            ["terrain", "Reds", "Blues", "Greens", "cividis", "magma", "viridis", "twilight", "cool", "coolwarm", "spring", "summer", "autumn", "winter"],
                            key=f"cmap_{file_info.get('name')}"
                        )
                        cmap = plt.get_cmap(cmap_choice)
                        filled_vals = gdf_sample[color_attr].fillna(0)
                        unique_vals = filled_vals.unique()
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
                        # color_attrがなければ全てにデフォルト色を設定
                        color_choice = st.sidebar.selectbox(
                            "カラーを選択",
                            ["Red", "Green", "Blue", "Purple", "Yellow", "Orange", "Black", "White"],
                            key=f"color_{file_info.get('name')}"
                        )
                        # 選択肢に対応するRGBAの値（最後の値は透明度）
                        color_dict = {
                            "Red": [255, 0, 0, 160],
                            "Green": [0, 255, 0, 160],
                            "Blue": [0, 0, 255, 160],
                            "Purple": [128, 0, 128, 160],
                            "Yellow": [255, 255, 0, 160],
                            "Orange": [255, 165, 0, 160],
                            "Black": [0, 0, 0, 160],
                            "White": [255, 255, 255, 160]
                        }
                        get_color_expr = color_dict.get(color_choice, [200, 30, 0, 160])
                        for feature in geojson_data["features"]:
                            feature["properties"]["get_color"] = get_color_expr
                    # 座標の中心は gdf の全体境界から計算
                    bounds = gdf_sample.total_bounds  # [minx, miny, maxx, maxy]
                    center_lat = (bounds[1] + bounds[3]) / 2
                    center_lon = (bounds[0] + bounds[2]) / 2
                    all_lat.append(center_lat)
                    all_lon.append(center_lon)
                    # ジオメトリの種類によって処理を分ける
                    if gdf_sample.geometry.geom_type.iloc[0] == "Point":
                        # if st.button("アイコンで表示", key=f"icon_button_{file_name}"):
                        #     # アイコンのアトラス（1枚の画像に複数のアイコンが含まれる画像）と、アイコンのマッピング情報を設定
                        #     icon_atlas = "./icon-atlas.png"
                        #     icon_mapping = {
                        #         "marker": {"x": 0, "y": 0, "width": 128, "height": 128, "mask": True},
                        #         }
                        #     icon_layer = pdk.Layer(
                        #         "IconLayer",
                        #         data=gdf_sample,
                        #         get_icon="icon",
                        #         get_position="geometry.coordinates",
                        #         sizeScale=15,
                        #         iconAtlas=icon_atlas,
                        #         iconMapping=icon_mapping,
                        #     )
                        #     map_layers.append(icon_layer)
                        # elif st.button("ポイントで表示", key=f"point_button_{file_name}"):
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
    # Plotly 用グラフ用変数を初期化
    plotly_fig = None
    plotly_fig1 = None
    plotly_fig2 = None
    st.sidebar.header("グラフの設定")
    if len(all_entries) == 0:
        st.sidebar.error("表示するファイルがありません。")
    else:
        # 対象ファイルの選択
        file_options = [fi["name"] for fi in all_entries if "name" in fi]
        file_choice = st.sidebar.selectbox("ファイルを選択", options=file_options)
        # 選択された file_info を取得
        file_info = next(fi for fi in all_entries if fi.get("name") == file_choice)
        df = file_info.get("preview", None)
        if df is None:
            st.error("選択されたファイルのプレビューがありません。")
        elif isinstance(df, pd.DataFrame) or isinstance(df, gpd.GeoDataFrame):
            # グラフの種類の選択
            graph_type = st.sidebar.selectbox("グラフの種類を選択", options=["散布図", "積み上げ縦棒グラフ", "円グラフ"])
            # カラムの選択
            cols = df.columns.tolist() + [None]
            default_index = len(cols) - 1
            col1 = st.sidebar.selectbox("1つ目のカラムを選択", options=cols, key="plot_col1", index=default_index)
            col2 = st.sidebar.selectbox("2つ目のカラムを選択(オプション)", options=cols, key="plot_col2", index=default_index)
            # グラフ作成
            if graph_type == "散布図":
                try:
                    df_numeric = df[[col1, col2]].apply(pd.to_numeric, errors="coerce")
                    plotly_fig = px.scatter(df_numeric, x=col1, y=col2, title="散布図")
                except Exception as e:
                    st.error(f"散布図作成エラー: {e}")
            elif graph_type == "積み上げ縦棒グラフ":
                try:
                    # col1 のグループ（文字列のシリーズ）を取得
                    group1 = group_by_range(df[col1], max_categories=5)[1]
                    if col2 is not None:
                        # col2 も指定されている場合は、両方のグループのクロス集計を行い積み上げグラフを作成
                        group2 = group_by_range(df[col2], max_categories=5)[1]
                        ctab = pd.crosstab(group1, group2)
                        fig = go.Figure()
                        for cat in ctab.columns:
                            fig.add_trace(go.Bar(
                                x=ctab.index,
                                y=ctab[cat],
                                name=str(cat)
                            ))
                        fig.update_layout(barmode='stack', title="積み上げ縦棒グラフ")
                    else:
                        # col2 が None の場合は、col1 のカウントを単一の棒グラフで表示
                        counts = group1.value_counts().sort_index()
                        fig = go.Figure(data=[go.Bar(
                            x=counts.index,
                            y=counts.values
                        )])
                        fig.update_layout(title=f"{col1} の分布")
                    plotly_fig = fig
                except Exception as e:
                    st.error(f"積み上げ縦棒グラフ作成エラー: {e}")
            elif graph_type == "円グラフ":
                try:
                    # col1 のグループ（文字列のシリーズ）を取得
                    group1 = group_by_range(df[col1], max_categories=5)[1]
                    if col2 is not None:
                        group2 = group_by_range(df[col2], max_categories=5)[1]
                        plotly_fig1 = px.pie(df, names=group1, title=f"{col1} の分布")
                        plotly_fig2 = px.pie(df, names=group2, title=f"{col2} の分布")
                    else:
                        # col2 が None の場合は、col1 の分布のみ表示
                        plotly_fig = px.pie(df, names=group1, title=f"{col1} の分布")
                except Exception as e:
                    st.error(f"円グラフ作成エラー: {e}")
        else:
            st.error("選択されたファイルは適切な形式ではありません。")

    # --- 上下レイアウトで表示 ---
    top_container = st.container()
    bottom_container = st.container()
    
    with top_container:
        if deck_chart is not None:
            st.pydeck_chart(deck_chart, use_container_width=True)
        else:
            st.info("表示する地図レイヤーがありません。")
    
    with bottom_container:
        if plotly_fig is not None:
            st.plotly_chart(plotly_fig, use_container_width=True)
        elif plotly_fig1 is not None and plotly_fig2 is not None:
            st.plotly_chart(plotly_fig1, use_container_width=True)
            st.plotly_chart(plotly_fig2, use_container_width=True)
        else:
            st.info("表示するグラフデータがありません。")

def main():
    st.title("高解像度熱中症リスクダッシュボード by HITS")
    
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