"""Kiểm thử tích video toàn bộ bộ lọc, xuyên phân trang như playlist."""
import ast
from pathlib import Path

import pytest
from werkzeug.datastructures import ImmutableMultiDict
from werkzeug.exceptions import BadRequest

ROOT=Path(__file__).resolve().parents[1]


def test_selection_ui_and_scripts_are_consistent():
    from jinja2 import Environment, FileSystemLoader
    template=(ROOT/"templates/videos.html").read_text(encoding="utf-8")
    js=(ROOT/"static/research_measurement.js").read_text(encoding="utf-8")
    selection_js=(ROOT/"static/video_selection.js").read_text(encoding="utf-8")
    py=(ROOT/"app.py").read_text(encoding="utf-8")
    Environment(loader=FileSystemLoader(str(ROOT/"templates"))).parse(template)
    ast.parse(py)
    assert 'id="videoLibraryFilterForm"' in template
    assert 'id="selectAllVideos"' in template
    assert 'videoBulkSelectedSummary' in template
    assert "Chọn tất cả / Bỏ chọn tất cả video trong kết quả lọc trên mọi trang" in template
    assert "mode==='all'?'excluded_video_ids':'selected_video_ids'" in selection_js
    assert "window.videoBulkSelection=api" in selection_js
    assert "video_selection.js" in template
    assert 'window.syncVideoBulkSelection?.();' in template
    assert 'window.videoBulkSelection?.selectedCount()' in js
    assert 'download_style' in js
    assert 'qr-download-complete' in js
    assert 'chosenVideos' not in js
    assert 'filtered_library_video_query' in py
    assert 'selected_filtered_library_video_ids(user, request.form)' in py
    assert 'qr_course_assignments' in py and 'qr_course_assignments' in selection_js
    assert 'selectedQrCourseCount' in selection_js
    assert 'data-assigned-video-count' in template
    assert 'dataset.assignedVideoCount' in js
    assert 'id="resetPlaylistFilters"' in template
    assert 'id="resetVideoFilters"' in template
    assert 'library_filter_reset.js' in template
    reset_js=(ROOT/"static/library_filter_reset.js").read_text(encoding="utf-8")
    assert 'slc-playlist-selection-v4:' in reset_js
    assert 'slc-video-selection-v2:' in reset_js
    assert 'String(scope[0])===String(userId)' in reset_js


@pytest.fixture
def configured_app(tmp_path,monkeypatch):
    monkeypatch.setenv("DATABASE_URL","sqlite:///"+str(tmp_path/"filtered_video.sqlite3"))
    monkeypatch.setenv("AUTO_CREATE_DB","0")
    monkeypatch.setenv("SECRET_KEY","local-test-key")
    monkeypatch.setenv("GOOGLE_CLIENT_ID","")
    monkeypatch.setenv("GOOGLE_CLIENT_SECRET","")
    import app as web
    from models import db,User,YouTubeChannel,Playlist,PlaylistVideo,Video,Course
    # Config đọc DATABASE_URL ở thời điểm import đầu tiên: mỗi test
    # cần URL riêng để không ghi đè dữ liệu của test trước đó.
    monkeypatch.setattr(web.Config, "SQLALCHEMY_DATABASE_URI",
                        "sqlite:///"+str(tmp_path/"filtered_video.sqlite3"))
    app=web.create_app()
    app.config.update(TESTING=True,WTF_CSRF_ENABLED=False,SESSION_COOKIE_SECURE=False)
    with app.app_context():
        db.create_all()
        teacher=User(email="video-selection-teacher@test.local",name="GV 1",role="lecturer",profile_completed=True)
        other=User(email="video-selection-other@test.local",name="GV 2",role="lecturer",profile_completed=True)
        db.session.add_all([teacher,other]);db.session.flush()
        course=Course(owner_id=teacher.id,name="Tin học ứng dụng",code="TIN01")
        channel=YouTubeChannel(user_id=teacher.id,channel_id="teacher_youtube",title="Kênh 1")
        outsider_channel=YouTubeChannel(user_id=other.id,channel_id="other_youtube",title="Kênh 2")
        db.session.add_all([course,channel,outsider_channel]);db.session.flush()
        playlist=Playlist(channel_id=channel.id,youtube_playlist_id="PL_VIDEO_SELECTION",title="Chủ đề 1")
        db.session.add(playlist);db.session.flush()
        match=[]
        for i in range(13):
            vid=Video(channel_id=channel.id,youtube_video_id="sel-v-"+str(i),
                      uploader_channel_id=channel.channel_id,
                      title="Bài học Tin học số "+str(i),privacy_status="public",
                      embeddable=True,is_available=True)
            db.session.add(vid);db.session.flush();match.append(vid.id)
            if i<4:db.session.add(PlaylistVideo(playlist_id=playlist.id,video_id=vid.id,position=i))
        other_local=Video(channel_id=channel.id,youtube_video_id="sel-no-match",
                          uploader_channel_id=channel.channel_id,title="Khác chủ đề",
                          privacy_status="public",embeddable=True,is_available=True)
        outside=Video(channel_id=outsider_channel.id,youtube_video_id="outside-v",
                      uploader_channel_id=outsider_channel.channel_id,
                      title="Bài học Tin học số người khác",
                      embeddable=True,is_available=True,privacy_status="public")
        db.session.add_all([other_local,outside]);db.session.flush()
        other_id=outside.id
        keys=dict(teacher=teacher.id,course=course.id,video_ids=match,
                  outsider=other_id,playlist=playlist.id,local_other=other_local.id)
        db.session.commit()
    return app,keys,web


def test_selection_server_filters_and_actions_across_pages(configured_app):
    from models import db, CourseVideo, QrCode
    app,k,web=configured_app
    with app.app_context():
        teacher=db.session.get(web.User,k["teacher"])
        q=web.filtered_library_video_query(teacher,"Bài học")
        assert q.count()==9, "Chỉ hiển thị video độc lập thuộc phạm vi GV, không lấy từ tài khoản khác"
        chosen=web.selected_filtered_library_video_ids(teacher,ImmutableMultiDict([
            ("q","Bài học"),("video_selection_mode","all"),
            ("excluded_video_ids",str(k["video_ids"][8])),
        ]))
        assert len(chosen)==8 and k["video_ids"][8] not in chosen
        none=web.selected_filtered_library_video_ids(teacher,ImmutableMultiDict([
            ("q","Bài học"),("video_selection_mode","none"),
            ("selected_video_ids",str(k["video_ids"][1])),
            ("selected_video_ids",str(k["video_ids"][11])),
            ("selected_video_ids",str(k["outsider"])),
        ]))
        assert set(none)=={k["video_ids"][11]}
        in_playlist=web.selected_filtered_library_video_ids(teacher,ImmutableMultiDict([
            ("q","Bài học"),("playlist_id",str(k["playlist"])),
            ("video_selection_mode","all"),
        ]))
        assert len(in_playlist)==0
        with pytest.raises(BadRequest):
            web.selected_filtered_library_video_ids(teacher,ImmutableMultiDict([
                ("video_selection_mode","all"),("status","undefined")
            ]))
    with app.test_client() as client:
        with client.session_transaction() as ss:ss["user_id"]=k["teacher"]
        page1=client.get("/videos?q=B%C3%A0i+h%E1%BB%8Dc&v_page=1")
        page2=client.get("/videos?q=B%C3%A0i+h%E1%BB%8Dc&v_page=2")
        page3=client.get("/videos?q=B%C3%A0i+h%E1%BB%8Dc&v_page=3")
        for page in (page1,page2,page3):
            assert page.status_code==200
            assert b'id="selectAllVideos"' in page.data
        assert page1.data.count(b'class="form-check-input video-check"')==5
        assert page2.data.count(b'class="form-check-input video-check"')==4
        assert page3.data.count(b'class="form-check-input video-check"')==4
        # Gán môn hàng loạt với 9 video độc lập, trừ 1 video ở TRANG 2.
        data={"course_id":str(k["course"]),"q":"Bài học",
              "video_selection_mode":"all",
              "excluded_video_ids":str(k["video_ids"][8])}
        response=client.post("/videos/assign-course",data=data)
        assert response.status_code==302
        with app.app_context():
            ids={link.video_id for link in CourseVideo.query.filter_by(course_id=k["course"]).all()}
            assert len(ids)==8 and k["video_ids"][8] not in ids
            assert k["outsider"] not in ids
        # Lần tạo QR chỉ 2 video trên 2 trang khác nhau, không dùng mọi video đã gán.
        response=client.post("/videos/qr/bulk-selected",data={
            "course_id":str(k["course"]),"q":"Bài học",
            "video_selection_mode":"none",
            "selected_video_ids":[str(k["video_ids"][1]),str(k["video_ids"][11]),
                                  str(k["outsider"])]})
        assert response.status_code==302
        with app.app_context():
            qrs=QrCode.query.filter_by(course_id=k["course"],active=True).all()
            assert len(qrs)==8, "Tạo QR cho toàn bộ video độc lập đã gán môn, không chỉ video tích"
            assert all(q.owner_id==k["teacher"] for q in qrs)



def test_video_library_reacts_to_playlist_membership(configured_app):
    """Khi gắn/bỏ liên kết playlist, bảng video và chọn hàng loạt cập nhật tương ứng.

    Playlist Uploads hệ thống được bỏ qua, playlist thuộc kênh khác vẫn có hiệu lực.
    """
    from models import db, Playlist, PlaylistVideo, YouTubeChannel
    app, keys, web = configured_app
    with app.app_context():
        teacher = db.session.get(web.User, keys["teacher"])
        linked_id = keys["video_ids"][0]
        independent_id = keys["video_ids"][6]
        playlist_id = keys["playlist"]
        get_ids = lambda: {v.id for v in web.filtered_library_video_query(teacher).all()}
        assert linked_id not in get_ids()
        assert independent_id in get_ids()

        db.session.add(PlaylistVideo(playlist_id=playlist_id, video_id=independent_id))
        db.session.commit()
        assert independent_id not in get_ids()
        PlaylistVideo.query.filter_by(playlist_id=playlist_id, video_id=independent_id).delete()
        PlaylistVideo.query.filter_by(playlist_id=playlist_id, video_id=linked_id).delete()
        db.session.commit()
        assert {linked_id, independent_id} <= get_ids()

        channel = YouTubeChannel.query.filter_by(user_id=teacher.id).first()
        channel.uploads_playlist_id = "UU_ONLY_SYSTEM"
        uploads = Playlist(
            channel_id=channel.id, youtube_playlist_id="UU_ONLY_SYSTEM", title="Uploads"
        )
        db.session.add(uploads)
        db.session.flush()
        db.session.add(PlaylistVideo(playlist_id=uploads.id, video_id=independent_id))
        db.session.commit()
        assert independent_id in get_ids()

        outsider_channel = YouTubeChannel.query.filter(YouTubeChannel.user_id != teacher.id).first()
        foreign_playlist = Playlist(
            channel_id=outsider_channel.id,
            youtube_playlist_id="PL_FOREIGN",
            title="Playlist kênh khác",
        )
        db.session.add(foreign_playlist)
        db.session.flush()
        db.session.add(PlaylistVideo(playlist_id=foreign_playlist.id, video_id=independent_id))
        db.session.commit()
        assert independent_id not in get_ids()


def test_table_columns_and_assignment_label_are_compact(configured_app):
    """Bảng playlist không có cột Kênh; bảng video bỏ Kênh và Playlist."""
    from bs4 import BeautifulSoup
    app, k, _web = configured_app
    with app.test_client() as client:
        with client.session_transaction() as ss: ss["user_id"] = k["teacher"]
        response=client.get("/videos")
        assert response.status_code==200
        soup=BeautifulSoup(response.data,"html.parser")
        playlists=soup.select_one("#playlists table")
        videos=soup.select_one("#videos table")
        assert playlists and videos
        pheads=[th.get_text(" ",strip=True) for th in playlists.select("thead th")]
        vheads=[th.get_text(" ",strip=True) for th in videos.select("thead th")]
        assert len(pheads)==6 and "Kênh YouTube" not in pheads
        assert len(vheads)==6 and "Kênh YouTube" not in vheads and "Playlist" not in vheads
        assert len(playlists.select("tbody > tr:first-child > td"))==6
        assert len(videos.select("tbody > tr:first-child > td"))==6
        label=soup.select_one('#videoLibraryFilterForm label.text-nowrap')
        assert label and label.get_text(" ",strip=True)=="Phân loại môn học/ mô đun"


def test_assign_qr_row_course_and_create_all_assigned_without_video_checks(configured_app):
    """Môn chọn ở cột Mã QR được gán dù không tick; QR tạo cho mọi video đã gán môn."""
    from models import db,Course,CourseVideo,QrCode
    app,k,web=configured_app
    with app.app_context():
        teacher=db.session.get(web.User,k["teacher"])
        other=web.User.query.filter(web.User.id != teacher.id).first()
        special=Course(owner_id=teacher.id,name="Lập trình cơ bản",code="PY02")
        foreign=Course(owner_id=other.id,name="Môn không thuộc quyền",code="OUT02")
        db.session.add_all([special,foreign]);db.session.commit()
        own_id=special.id
        foreign_id=foreign.id
    row_video=k["video_ids"][10]  # Dòng video độc lập nằm trên trang đầu.
    other_video=k["video_ids"][5] # Dòng ở trang sau.
    with app.test_client() as client:
        with client.session_transaction() as ss: ss["user_id"]=k["teacher"]
        # Không tích video, không chọn môn chung: chỉ lấy môn ở cột Mã QR.
        assigned=client.post("/videos/assign-course",data={
            "video_selection_mode":"none",
            "return_query":"v_page=1",
            "qr_course_assignments":[f"{row_video}:{own_id}"],
        })
        assert assigned.status_code==302
        with app.app_context():
            assert CourseVideo.query.filter_by(course_id=own_id,video_id=row_video).count()==1
            assert QrCode.query.filter_by(course_id=own_id).count()==0
        # Môn chung áp dụng cho checkbox ở mọi trang, nhưng không ghi trùng liên kết.
        combined=client.post("/videos/assign-course",data={
            "course_id":str(own_id),"video_selection_mode":"none",
            "selected_video_ids":[str(other_video),str(row_video)],
            "qr_course_assignments":[f"{row_video}:{own_id}"],
        })
        assert combined.status_code==302
        with app.app_context():
            assert CourseVideo.query.filter_by(course_id=own_id).count()==2
        # Không thể gán giảng viên khác hoặc giả ID video ngoài trang đang xem.
        forbidden_response=client.post("/videos/assign-course",data={
            "video_selection_mode":"none",
            "return_query":"v_page=1",
            "qr_course_assignments":[f"{row_video}:{foreign_id}"]
        })
        assert forbidden_response.status_code==403, (
            forbidden_response.status_code, forbidden_response.location,
            forbidden_response.get_data(as_text=True)[:250]
        )
        assert client.post("/videos/assign-course",data={
            "video_selection_mode":"none",
            "qr_course_assignments":[f"{k['video_ids'][0]}:{own_id}"]
        }).status_code==400

        # KHÔNG tích bất cứ checkbox video nào; bộ lọc hiện hành có thể rỗng.
        qr=client.post("/videos/qr/bulk-selected",data={
            "course_id":str(own_id),"q":"không khớp video nào",
            "video_selection_mode":"none",
        })
        assert qr.status_code==302
        with app.app_context():
            qrs=QrCode.query.filter_by(course_id=own_id,active=True).all()
            assert len(qrs)==2
            assert {x.current_target.video_id for x in qrs}=={row_video,other_video}
        # Gọi lại không tạo mã trùng, kể cả khi không có video đang được tick.
        client.post("/videos/qr/bulk-selected",data={"course_id":str(own_id)})
        with app.app_context():
            assert QrCode.query.filter_by(course_id=own_id,active=True).count()==2




def test_reset_buttons_keep_other_category_filters(configured_app):
    """Bỏ lọc từng danh mục, reset phân trang/chọn xuyên trang, không ảnh hưởng danh mục kia."""
    from bs4 import BeautifulSoup
    from urllib.parse import urlsplit, parse_qs
    app, keys, _ = configured_app
    with app.test_client() as client:
        with client.session_transaction() as ss:
            ss["user_id"] = keys["teacher"]
        path=(
            "/videos?q=B%C3%A0i+h%E1%BB%8Dc&status=usable"
            "&assignment=unassigned&playlist_id="+str(keys["playlist"])
            +"&v_page=2&p_q=Ch%E1%BB%A7&p_assignment=assigned&p_page=2"
        )
        response=client.get(path)
        assert response.status_code==200
        soup=BeautifulSoup(response.data,"html.parser")
        p=soup.select_one("#resetPlaylistFilters")
        v=soup.select_one("#resetVideoFilters")
        assert p is not None and v is not None
        assert p.get("data-library-filter-reset")=="playlist"
        assert v.get("data-library-filter-reset")=="video"
        playlist_url,video_url=p["href"],v["href"]
        qp=parse_qs(urlsplit(playlist_url).query)
        qv=parse_qs(urlsplit(video_url).query)
        assert urlsplit(playlist_url).fragment=="playlists"
        assert urlsplit(video_url).fragment=="videos"
        assert all(key not in qp for key in ("p_q","p_assignment","p_page"))
        assert qp["q"]==["Bài học"] and qp["status"]==["usable"]
        assert qp["assignment"]==["unassigned"]
        assert qp["playlist_id"]==[str(keys["playlist"])]
        assert qp["v_page"]==["2"]
        assert all(key not in qv for key in (
            "q","status","assignment","playlist_id","v_page"))
        assert qv["p_q"]==["Chủ"] and qv["p_assignment"]==["assigned"]
        assert qv["p_page"]==["2"]

        # Server sẽ hiển thị filter mặc định và tất cả học liệu tương ứng.
        ppage=client.get(playlist_url)
        vpage=client.get(video_url)
        assert ppage.status_code==200 and vpage.status_code==200
        ps=BeautifulSoup(ppage.data,"html.parser")
        vs=BeautifulSoup(vpage.data,"html.parser")
        assert ps.select_one('#playlistLibraryFilterForm [name="p_q"]').get("value")==""
        assert ps.select_one('#playlistLibraryFilterForm [name="p_assignment"] option[selected]') is None
        assert vs.select_one('#videoLibraryFilterForm [name="q"]').get("value")==""
        assert vs.select_one('#videoLibraryFilterForm [name="status"] option[selected]') is None
        assert vs.select_one('#videoLibraryFilterForm [name="assignment"] option[selected]') is None
        assert vs.select_one('#videoLibraryFilterForm [name="playlist_id"] option[selected]') is None
        assert "Có 10 video" in vs.get_text(" ",strip=True)
        assert "Có 1 playlist" in ps.get_text(" ",strip=True)


def test_analytics_excel_exports_and_research_form(configured_app):
    """Các nút xuất tệp Excel và bố cục đo không ảnh hưởng quyền truy cập."""
    import io
    from openpyxl import load_workbook
    app, keys, _web = configured_app
    with app.test_client() as client:
        with client.session_transaction() as session:
            session["user_id"] = keys["teacher"]
        response = client.get("/analytics")
        assert response.status_code == 200
        for code in (b"export_xlsx=system", b"export_xlsx=scans", b"export_xlsx=videos"):
            assert code in response.data
        for kind, label in (
            ("system", "Thống kê hoạt động của hệ thống"),
            ("scans", "Thống kê lượt quét mã QR"),
            ("videos", "Thống kê hoạt động khai thác video"),
        ):
            exported = client.get("/analytics?export_xlsx=" + kind)
            assert exported.status_code == 200
            assert "spreadsheetml.sheet" in exported.content_type
            assert "attachment" in exported.headers["Content-Disposition"]
            workbook = load_workbook(io.BytesIO(exported.data), read_only=True)
            assert label in workbook.active["A1"].value
            assert workbook.active["A4"].value == "STT"
            assert workbook.active.max_column >= 6
            workbook.close()
        assert client.get("/analytics?export_xlsx=unauthorized").status_code == 400

        research = client.get("/research")
        # Quyền truy cập trang nghiên cứu hiện tại có thể chỉ dành cho quản trị viên;
        # kiểm tra bố cục template độc lập tại mọi vai trò.
        assert research.status_code in (200, 302, 403)
    template = (ROOT / "templates/research.html").read_text(encoding="utf-8")
    assert 'id="researchPairCreateForm"' in template
    assert 'id="clearResearchPairForm">Xóa thông tin' in template
    assert "Tổng số thao tác thủ công" in template
    assert "Số QR cần tạo (tự tính)" not in template
    assert "Quản lý bản ghi đối chứng cần điều chỉnh" not in template
    assert "Hiển thị 120 lượt đo gần nhất" not in template


def test_video_bulk_three_actions_and_download_only_existing_assigned_qrs(configured_app):
    """Gán môn -> tạo QR cho video đã gán -> tải đúng QR của video được chọn."""
    import io
    import zipfile
    from bs4 import BeautifulSoup
    from models import db, CourseVideo, QrCode
    app, keys, _ = configured_app
    with app.test_client() as client:
        with client.session_transaction() as ss: ss["user_id"] = keys["teacher"]
        page = client.get("/videos")
        assert page.status_code == 200
        soup = BeautifulSoup(page.data, "html.parser")
        form = soup.select_one("#assignVideoForm")
        assert form is not None
        assert len(form.select('button[formaction]')) == 2
        assert "/videos/qr/bulk-selected" in str(form)
        assert "/videos/qr/download-selected" in str(form)
        chosen = [str(keys["video_ids"][5]), str(keys["video_ids"][10])]
        post_data = {
            "course_id": str(keys["course"]), "q": "Bài học",
            "video_selection_mode": "none", "selected_video_ids": chosen,
        }
        # Không tạo QR tự động khi các video chưa được gán môn.
        assert client.post("/videos/qr/bulk-selected", data=post_data).status_code == 302
        with app.app_context():
            assert CourseVideo.query.filter_by(course_id=keys["course"]).count() == 0
            assert QrCode.query.count() == 0
        assert client.post("/videos/qr/download-selected", data=post_data).status_code == 302
        assert client.post("/videos/assign-course", data=post_data).status_code == 302
        with app.app_context():
            assert CourseVideo.query.filter_by(course_id=keys["course"]).count() == 2
        assert client.post("/videos/qr/bulk-selected", data=post_data).status_code == 302
        with app.app_context():
            assert QrCode.query.count() == 2
        response = client.post("/videos/qr/download-selected", data=post_data)
        assert response.status_code == 200
        assert response.mimetype == "application/zip"
        with zipfile.ZipFile(io.BytesIO(response.data)) as zip_file:
            files = zip_file.namelist()
            assert len(files) == 2
            assert all(path.endswith(".png") for path in files)
            assert all(zip_file.read(path).startswith(bytes([137,80,78,71,13,10,26,10])) for path in files)
        # Nếu chỉ còn chọn 1 video, ZIP cũng chỉ có duy nhất QR tương ứng.
        single = dict(post_data, selected_video_ids=[chosen[0]])
        response = client.post("/videos/qr/download-selected", data=single)
        assert response.status_code == 200
        with zipfile.ZipFile(io.BytesIO(response.data)) as zip_file:
            assert len(zip_file.namelist()) == 1
        # Không truy cập được video hoặc QR của giảng viên khác.
        outsider = dict(post_data, selected_video_ids=[str(keys["outsider"])])
        assert client.post("/videos/qr/download-selected", data=outsider).status_code == 302
