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
    assert 'qr_course_assignments' in py and 'qr_course_assignments' in template
    assert 'data-video-row-assign' in selection_js
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
        # Giao diện đang bắt 403 và chuyển về trang chủ kèm thông báo từ chối.
        assert forbidden_response.status_code==302 and forbidden_response.location=="/"
        with app.app_context():
            assert CourseVideo.query.filter_by(course_id=foreign_id,video_id=row_video).count()==0
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




def test_qr_column_overrides_previous_course_and_selected_bulk_course(configured_app):
    """Tình huống thực: 1 video đã gán Python -> chọn Toán rời rạc ở cột QR;
    video khác tích ô -> gán Python. Không cấp trùng và không xóa QR cũ.
    """
    from bs4 import BeautifulSoup
    from models import db, Course, Video, CourseVideo, QrCode
    app, k, web = configured_app
    # Video mới nhất nằm ở dòng đầu của trang 1 (sắp xếp Video.id giảm dần).
    first_video_id = k["local_other"]
    checked_video_id = k["video_ids"][12]
    with app.app_context():
        teacher = db.session.get(web.User, k["teacher"])
        python_course = db.session.get(Course, k["course"])
        first_video = db.session.get(Video, first_video_id)
        math_course = Course(owner_id=teacher.id, name="Toán rời rạc", code="MATH01")
        db.session.add(math_course)
        db.session.flush()
        math_course_id = math_course.id
        link, _ = web.ensure_course_video_link(python_course, first_video, teacher)
        qr, was_created = web.create_qr_for_course_video(
            python_course, first_video, teacher, link
        )
        assert was_created
        old_qr_id = qr.id
        db.session.commit()
    with app.test_client() as client:
        with client.session_transaction() as ss:
            ss["user_id"] = k["teacher"]
        # Không tích video đầu tiên. Môn Toán chọn ở cột QR phải THAY THẾ Python.
        response = client.post("/videos/assign-course", data={
            "course_id": str(k["course"]),
            "video_selection_mode": "none",
            "selected_video_ids": [str(checked_video_id)],
            "qr_course_assignments": [f"{first_video_id}:{math_course_id}"],
            "return_query": "v_page=1",
        })
        assert response.status_code == 302
        with app.app_context():
            assert CourseVideo.query.filter_by(
                course_id=k["course"], video_id=checked_video_id
            ).count() == 1
            assert CourseVideo.query.filter_by(
                course_id=k["course"], video_id=first_video_id
            ).count() == 0, "Video đầu tiên không được giữ gán môn Python"
            assert CourseVideo.query.filter_by(
                course_id=math_course_id, video_id=first_video_id
            ).count() == 1
            assert CourseVideo.query.filter_by(
                course_id=math_course_id, video_id=checked_video_id
            ).count() == 0
            qr = db.session.get(QrCode, old_qr_id)
            assert qr.active and qr.course_id == k["course"]
            assert qr.current_target.video_id == first_video_id

        page = client.get("/videos")
        assert page.status_code == 200
        soup = BeautifulSoup(page.data, "html.parser")
        first = soup.select_one(f"#video-{first_video_id}")
        selected = soup.select_one(f"#video-{checked_video_id}")
        assert first is not None and selected is not None
        assert [node.get_text(" ", strip=True) for node in
                first.select("td:nth-child(3) .badge")] == ["Toán rời rạc"]
        assert [node.get_text(" ", strip=True) for node in
                selected.select("td:nth-child(3) .badge")] == ["Tin học ứng dụng"]

        # Ngay cả khi tích chính video đầu tiên, lựa chọn cột QR vẫn ưu tiên.
        response = client.post("/videos/assign-course", data={
            "course_id": str(k["course"]),
            "video_selection_mode": "none",
            "selected_video_ids": [str(first_video_id), str(checked_video_id)],
            "qr_course_assignments": [f"{first_video_id}:{math_course_id}"],
            "return_query": "v_page=1",
        })
        assert response.status_code == 302
        with app.app_context():
            assert CourseVideo.query.filter_by(
                course_id=k["course"], video_id=first_video_id
            ).count() == 0
            assert CourseVideo.query.filter_by(
                course_id=math_course_id, video_id=first_video_id
            ).count() == 1


def test_remove_long_video_library_guide():
    template = (ROOT / "templates/videos.html").read_text(encoding="utf-8")
    assert "Ô tích chọn video trên <strong>mọi trang</strong>" not in template
    assert "Nút <strong>Tạo QR</strong> áp dụng cho tất cả video" not in template


def test_qr_row_selections_are_native_form_controls_and_cache_busted(configured_app):
    """HTML thuần phải gửi được môn của từng dòng ngay cả khi submit JS bị chặn."""
    from bs4 import BeautifulSoup
    app, keys, _ = configured_app
    with app.test_client() as client:
        with client.session_transaction() as ss:
            ss["user_id"] = keys["teacher"]
        response = client.get("/videos")
        assert response.status_code == 200
        soup = BeautifulSoup(response.data, "html.parser")
        rows = soup.select("#videos tr.library-target-row")
        assert len(rows) == 5
        for row in rows:
            select = row.select_one(".video-qr-course-select")
            mirror = row.select_one("input[data-video-row-assign]")
            assert select is not None and mirror is not None
            assert "onchange" in select.attrs
            assert mirror.get("form") == "assignVideoForm"
            assert mirror.get("name") == "qr_course_assignments"
            assert mirror.has_attr("disabled")
            assert mirror.get("id") in select.get("onchange")
            assert row["id"].split("-")[-1] == mirror.get("data-video-row-assign")
        sources = [x.get("src", "") for x in soup.select("script[src]")]
        assert any("video_selection.js?v=row-mirror-20261126" in x for x in sources)


def test_first_fourth_row_qr_courses_and_one_checked_video_in_single_post(configured_app):
    """Hai dropdown QR (hàng 1,4) cùng chuyển sang Toán, ô tích giữ Python."""
    from models import db, Course, CourseVideo
    app, keys, web = configured_app
    first = keys["local_other"]          # trang 1 hàng 1
    fourth = keys["video_ids"][10]       # trang 1 hàng 4
    checked = keys["video_ids"][12]      # trang 1 hàng 2
    with app.app_context():
        teacher = db.session.get(web.User, keys["teacher"])
        python_course = db.session.get(Course, keys["course"])
        math_course = Course(owner_id=teacher.id, name="Toán rời rạc", code="MATH02")
        db.session.add(math_course)
        db.session.flush()
        math_id = math_course.id
        for vid in (first, fourth):
            video = db.session.get(web.Video, vid)
            web.ensure_course_video_link(python_course, video, teacher)
        db.session.commit()
    with app.test_client() as client:
        with client.session_transaction() as ss:
            ss["user_id"] = keys["teacher"]
        response = client.post("/videos/assign-course", data={
            "course_id": str(keys["course"]),
            "video_selection_mode": "none",
            "selected_video_ids": [str(checked)],
            # Hai input mirror, kèm mô phỏng 2 bản ghi do JS cũ sinh thêm.
            "qr_course_assignments": [
                f"{first}:{math_id}", f"{fourth}:{math_id}",
                f"{first}:{math_id}", f"{fourth}:{math_id}",
            ],
            "return_query": "v_page=1",
        })
        assert response.status_code == 302
        with app.app_context():
            for vid in (first, fourth):
                assert CourseVideo.query.filter_by(
                    course_id=math_id, video_id=vid
                ).count() == 1
                assert CourseVideo.query.filter_by(
                    course_id=keys["course"], video_id=vid
                ).count() == 0
            assert CourseVideo.query.filter_by(
                course_id=keys["course"], video_id=checked
            ).count() == 1
            assert CourseVideo.query.filter_by(
                course_id=math_id, video_id=checked
            ).count() == 0

        # Hai bản ghi cùng video nhưng chọn 2 môn khác nhau phải bị từ chối.
        response = client.post("/videos/assign-course", data={
            "course_id": str(keys["course"]),
            "video_selection_mode": "none",
            "qr_course_assignments": [
                f"{first}:{math_id}", f"{first}:{keys['course']}"
            ],
        })
        assert response.status_code == 400



def test_create_qr_all_assigned_courses_without_course_selection(configured_app):
    """Lỗi bản TEST: nút Tạo QR không được đòi chọn môn phía trên.

    Xử lý mọi video độc lập đã gán (nhiều môn và nhiều trang),
    kể cả khi tìm kiếm không khớp, và không tạo mã trùng khi bấm lại.
    """
    from urllib.parse import urlsplit
    from bs4 import BeautifulSoup
    from models import db, CourseVideo, QrCode, Course
    app, keys, web = configured_app
    video_python = keys["video_ids"][10]
    video_math = keys["video_ids"][5]
    course_python = keys["course"]
    with app.app_context():
        user = db.session.get(web.User, keys["teacher"])
        math = Course(owner_id=user.id, name="Toán rời rạc", code="MATH_ALL")
        db.session.add(math)
        db.session.commit()
        course_math = math.id

    with app.test_client() as client:
        with client.session_transaction() as ss:
            ss["user_id"] = keys["teacher"]
        response = client.post("/videos/assign-course", data={
            "course_id": str(course_python),
            "video_selection_mode": "none",
            "selected_video_ids": [str(video_python)],
            "return_query": "v_page=1",
        })
        assert response.status_code == 302
        response = client.post("/videos/assign-course", data={
            "course_id": str(course_math),
            "video_selection_mode": "none",
            "selected_video_ids": [str(video_math)],
            "return_query": "v_page=1",
        })
        assert response.status_code == 302
        with app.app_context():
            assert CourseVideo.query.filter(
                CourseVideo.course_id.in_([course_python, course_math])
            ).count() == 2

        # Không gửi course_id, không tích checkbox, tìm kiếm không có kết quả.
        created = client.post("/videos/qr/bulk-selected", data={
            "video_selection_mode": "none",
            "return_query": "q=khong-khop-video&v_page=1"
        })
        assert created.status_code == 302
        assert urlsplit(created.location).path == "/videos"
        assert urlsplit(created.location).fragment == "videos"
        page = client.get(created.location)
        assert page.status_code == 200
        page_text = page.get_data(as_text=True)
        assert "tạo 2 mã QR mới" in page_text
        assert "Bạn không có quyền truy cập chức năng này." not in page_text
        with app.app_context():
            qrs = QrCode.query.filter(QrCode.active.is_(True)).all()
            assert len(qrs) == 2
            assert {qr.course_id for qr in qrs} == {course_python, course_math}
            assert {qr.current_target.video_id for qr in qrs} == {video_python, video_math}
            ids = {qr.id for qr in qrs}
        # Bấm lại với môn chọn sai / còn giá trị cũ: vẫn chỉ xử lý dữ liệu
        # giảng viên được quyền quản lý, không sinh mã QR khác.
        repeated = client.post("/videos/qr/bulk-selected", data={
            "course_id": "999999",
            "video_selection_mode": "none"
        })
        assert repeated.status_code == 302
        assert urlsplit(repeated.location).path == "/videos"
        with app.app_context():
            assert {q.id for q in QrCode.query.filter(QrCode.active.is_(True)).all()} == ids
        message = client.get(repeated.location).get_data(as_text=True)
        assert "2 mã QR đã có" in message


def test_create_all_qrs_empty_library_warns_instead_of_forbidden(configured_app):
    """Không có video đã gán: cảnh báo tại Kho video, không về Tổng quan."""
    app, keys, _ = configured_app
    with app.test_client() as client:
        with client.session_transaction() as ss:
            ss["user_id"] = keys["teacher"]
        result = client.post("/videos/qr/bulk-selected", data={
            "video_selection_mode": "none"
        })
        assert result.status_code == 302
        assert result.location == "/videos#videos"
        response = client.get(result.location)
        html = response.get_data(as_text=True)
        assert "Chưa có video độc lập nào được gán môn" in html
        assert "Bạn không có quyền truy cập chức năng này." not in html


def test_create_all_qrs_bypasses_single_course_browser_preflight():
    js = (ROOT / "static/research_measurement.js").read_text(encoding="utf-8")
    html = (ROOT / "templates/videos.html").read_text(encoding="utf-8")
    app_text = (ROOT / "app.py").read_text(encoding="utf-8")
    assert "event.submitter?.formAction?.includes('/videos/qr/bulk-selected')" in js
    assert "Môn học/ mô đun áp dụng cho video tích chọn</label>" in html
    route = app_text.split('@app.post("/videos/qr/bulk-selected")')[1]
    route = route.split('@app.post("/videos/qr/download-selected")')[0]
    assert 'Course.owner_id == user.id' in route
    assert 'Course.active.is_(True)' in route
    assert 'request.form.get("course_id"' not in route



def test_only_row_course_assign_restores_course_picker(configured_app):
    """Gán chỉ tại cột Mã QR vẫn khôi phục môn nếu tất cả dòng cùng môn."""
    from urllib.parse import urlsplit, parse_qs
    from models import db, Course
    app, keys, web = configured_app
    with app.app_context():
        teacher = db.session.get(web.User, keys["teacher"])
        course = Course(owner_id=teacher.id, name="Toán rời rạc", code="MATH-ONLY-QR")
        db.session.add(course)
        db.session.commit()
        math_id = course.id
    with app.test_client() as client:
        with client.session_transaction() as ss:
            ss["user_id"] = keys["teacher"]
        response = client.post("/videos/assign-course", data={
            "video_selection_mode": "none",
            "qr_course_assignments": [f"{keys['video_ids'][10]}:{math_id}"],
            "return_query": "v_page=1"
        })
        assert response.status_code == 302
        assert parse_qs(urlsplit(response.location).query)["video_course_id"] == [str(math_id)]



def test_bulk_create_then_all_qr_download_and_row_buttons(configured_app):
    """Tạo QR mọi môn -> nút dòng sáng -> tải toàn bộ PNG không tích video."""
    import io
    import zipfile
    from bs4 import BeautifulSoup
    from models import db, Course, CourseVideo, QrCode
    app, keys, web = configured_app
    first_id, fourth_id = keys["video_ids"][12], keys["video_ids"][10]
    with app.app_context():
        teacher = db.session.get(web.User, keys["teacher"])
        math = Course(owner_id=teacher.id, name="Toán rời rạc", code="MATH-DOWNLOAD")
        db.session.add(math)
        db.session.commit()
        math_id = math.id
    with app.test_client() as client:
        with client.session_transaction() as session:
            session["user_id"] = keys["teacher"]
        for video_id, course_id in ((first_id, keys["course"]), (fourth_id, math_id)):
            assigned = client.post("/videos/assign-course", data={
                "course_id": str(course_id), "video_selection_mode": "none",
                "selected_video_ids": [str(video_id)], "return_query": "v_page=1"
            })
            assert assigned.status_code == 302
        created = client.post("/videos/qr/bulk-selected", data={
            "video_selection_mode": "none"
        })
        assert created.status_code == 302
        with app.app_context():
            assert QrCode.query.filter(QrCode.active.is_(True)).count() == 2

        page = client.get("/videos")
        assert page.status_code == 200
        soup = BeautifulSoup(page.data, "html.parser")
        assert soup.select_one('#assignVideoForm [name="download_scope"]')["value"] == "all_assigned"
        for video_id, course_id in ((first_id, keys["course"]), (fourth_id, math_id)):
            row = soup.select_one(f"#video-{video_id}")
            assert row is not None
            select = row.select_one(".video-qr-course-select")
            selected = select.select_one("option[selected]")
            assert selected and selected["value"] == str(course_id)
            assert selected.get("data-qr-png")
            assert selected.get("data-qr-filename") == (
                f"Bài học Tin học số {12 if video_id == first_id else 10}.png"
            )
            create_button = row.select_one(".video-qr-create")
            assert create_button is not None and not create_button.has_attr("disabled")
            assert row.select_one(".video-qr-download")

        response = client.post("/videos/qr/download-selected", data={
            "download_scope": "all_assigned",
            "video_selection_mode": "none",
        }, headers={"Accept": "application/json"})
        assert response.status_code == 200
        payload = response.get_json()
        assert payload["ok"] is True and payload["count"] == 2
        assert len(payload["files"]) == 2
        assert all(x["url"].endswith("/png") for x in payload["files"])
        assert len({x["id"] for x in payload["files"]}) == 2

        # Không cần chọn môn hay tích checkbox để tải ZIP.
        # Mỗi môn có thư mục riêng, giữ nguyên tên video bên trong.
        with app.app_context():
            python_course = db.session.get(Course, keys["course"])
            python_folder = web.qr_zip_course_folder(
                QrCode.query.filter_by(course_id=python_course.id).first()
            )
            math_folder = web.qr_zip_course_folder(
                QrCode.query.filter_by(course_id=math_id).first()
            )
        assert python_folder != math_folder
        response = client.post("/videos/qr/download-selected", data={
            "download_scope": "all_assigned",
        })
        assert response.status_code == 200
        assert response.mimetype == "application/zip"
        assert "Ma_QR_video_da_tao_tat_ca.zip" in response.headers["Content-Disposition"]
        with zipfile.ZipFile(io.BytesIO(response.data)) as archive:
            names = archive.namelist()
            assert set(names) == {
                f"{python_folder}/Bài học Tin học số 12.png",
                f"{math_folder}/Bài học Tin học số 10.png",
            }
            assert all(len(n.split("/")) == 2 for n in names)
            assert all(n.startswith((python_folder + "/", math_folder + "/"))
                       for n in names)
            assert all(archive.read(n).startswith(bytes([137, 80, 78, 71, 13, 10, 26, 10]))
                       for n in names)

        # Bấm tải lại không tạo mã mới.
        with app.app_context():
            assert QrCode.query.filter(QrCode.active.is_(True)).count() == 2


def test_download_all_qrs_without_created_items_shows_clear_error(configured_app):
    """Không có QR: trả thông báo rõ thay vì báo sai quyền hoặc im lặng."""
    app, keys, web = configured_app
    with app.test_client() as client:
        with client.session_transaction() as session:
            session["user_id"] = keys["teacher"]
        response = client.post("/videos/qr/download-selected", data={
            "download_scope": "all_assigned"
        }, headers={"Accept": "application/json"})
        assert response.status_code == 409
        result = response.get_json()
        assert not result["ok"]
        assert "Chưa có mã QR hợp lệ" in result["message"]


def test_download_all_js_has_no_checkbox_or_course_gate():
    """Luồng chọn thư mục/ZIP phải được chạy với nút Tải QR toàn bộ."""
    js = (ROOT / "static/research_measurement.js").read_text(encoding="utf-8")
    html = (ROOT / "templates/videos.html").read_text(encoding="utf-8")
    assert "form.querySelector('[name=\"download_scope\"]')?.value==='all_assigned'" in js
    assert "if(!allAssignedQrs){" in js
    assert "else if(isVideoBulk(form) && !allVideoQrs)" in js
    assert "create.hidden=hasQr;create.disabled=!select.value" in html



def test_playlist_bulk_qr_all_assigned_shows_three_actions_and_downloads_zip(configured_app):
    """Playlist như video: tạo mọi QR đã gán môn, nút Tạo ẩn và tải tất cả PNG."""
    import io
    import zipfile
    from bs4 import BeautifulSoup
    from models import db, Course, Playlist, PlaylistVideo, CoursePlaylist, QrCode, YouTubeChannel
    app, keys, web = configured_app
    first_playlist_id = keys["playlist"]
    with app.app_context():
        user = db.session.get(web.User, keys["teacher"])
        channel = YouTubeChannel.query.filter_by(user_id=user.id).first()
        math = Course(owner_id=user.id, name="Toán rời rạc", code="MATH-PL-ALL")
        second = Playlist(
            channel_id=channel.id, youtube_playlist_id="PL_SECOND",
            title="Playlist thứ hai", is_available=True
        )
        db.session.add_all([math, second])
        db.session.flush()
        db.session.add(PlaylistVideo(
            playlist_id=second.id, video_id=keys["video_ids"][1], position=0
        ))
        db.session.add_all([
            CoursePlaylist(course_id=keys["course"], playlist_id=first_playlist_id,
                           added_by=user.id, active=True),
            CoursePlaylist(course_id=math.id, playlist_id=second.id,
                           added_by=user.id, active=True),
        ])
        other = web.User.query.filter(web.User.id != user.id).first()
        foreign_channel = YouTubeChannel.query.filter_by(user_id=other.id).first()
        foreign_course = Course(owner_id=other.id, name="Môn người khác", code="EXT-PL")
        foreign_playlist = Playlist(
            channel_id=foreign_channel.id, youtube_playlist_id="PL_FOREIGN",
            title="Playlist người khác", is_available=True
        )
        db.session.add_all([foreign_course, foreign_playlist])
        db.session.flush()
        db.session.add_all([
            PlaylistVideo(playlist_id=foreign_playlist.id, video_id=keys["video_ids"][2], position=0),
            CoursePlaylist(course_id=foreign_course.id,
                           playlist_id=foreign_playlist.id,
                           added_by=other.id, active=True),
        ])
        db.session.commit()
        second_playlist_id = second.id
        math_id = math.id
        foreign_course_id = foreign_course.id

    with app.test_client() as client:
        with client.session_transaction() as session:
            session["user_id"] = keys["teacher"]
        response = client.post("/playlists/bulk-create-course-qrs", data={
            "course_id": str(foreign_course_id),
            "p_q": "không có kết quả",
            "playlist_selection_mode": "none",
            "selected_playlist_ids": [],
        })
        assert response.status_code == 302
        assert response.location.startswith("/videos") and "#playlists" in response.location
        with app.app_context():
            qrs = QrCode.query.filter_by(target_type="playlist", active=True).all()
            assert len(qrs) == 2
            assert {(q.course_id, q.playlist_id) for q in qrs} == {
                (keys["course"], first_playlist_id), (math_id, second_playlist_id)}
            original_ids = {q.id for q in qrs}
        # Bấm lại không tạo trùng, dù filter/ô tích hoặc course_id khác.
        client.post("/playlists/bulk-create-course-qrs", data={
            "playlist_selection_mode": "none"
        })
        with app.app_context():
            assert {q.id for q in QrCode.query.filter_by(
                target_type="playlist", active=True).all()} == original_ids

        page = client.get("/videos")
        assert page.status_code == 200
        soup = BeautifulSoup(page.data, "html.parser")
        assert soup.select_one('#playlistBulkActions [name="download_scope"]')["value"] == "all_assigned"
        create_btn = soup.select_one('#playlistBulkActions button[formaction*="bulk-create-course-qrs"]')
        assert "Tạo QR cho playlist đã gán MH/MĐ" in create_btn.get_text(" ", strip=True)
        assert create_btn.has_attr("formnovalidate")
        for playlist_id in (first_playlist_id, second_playlist_id):
            row = soup.select_one(f"#playlist-{playlist_id}")
            assert row is not None
            option = row.select_one(".playlist-qr-course-select option[selected]")
            assert option and option.get("data-qr-png")
            assert option.get("data-qr-filename") == (
                "Chủ đề 1.png" if playlist_id == first_playlist_id
                else "Playlist thứ hai.png"
            )
            assert row.select_one(".playlist-qr-create").has_attr("hidden")
            assert row.select_one(".playlist-qr-download") is not None
            assert row.select_one(".playlist-qr-retarget-toggle") is not None
            assert row.select_one(".playlist-qr-delete-form") is not None

        json_response = client.post("/playlists/qr/download-selected", data={
            "download_scope": "all_assigned", "playlist_selection_mode": "none"
        }, headers={"Accept": "application/json"})
        assert json_response.status_code == 200
        payload = json_response.get_json()
        assert payload["ok"] and payload["count"] == 2
        assert len({item["id"] for item in payload["files"]}) == 2
        assert all(item["url"].endswith("/png") for item in payload["files"])
        with app.app_context():
            python_qr = QrCode.query.filter_by(
                target_type="playlist", course_id=keys["course"]
            ).first()
            math_qr = QrCode.query.filter_by(
                target_type="playlist", course_id=math_id
            ).first()
            python_folder = web.qr_zip_course_folder(python_qr)
            math_folder = web.qr_zip_course_folder(math_qr)
        assert python_folder != math_folder
        zip_response = client.post("/playlists/qr/download-selected", data={
            "download_scope": "all_assigned"
        })
        assert zip_response.status_code == 200
        assert zip_response.mimetype == "application/zip"
        assert "Ma_QR_playlist_da_tao_tat_ca.zip" in zip_response.headers["Content-Disposition"]
        with zipfile.ZipFile(io.BytesIO(zip_response.data)) as archive:
            assert set(archive.namelist()) == {
                f"{python_folder}/Chủ đề 1.png",
                f"{math_folder}/Playlist thứ hai.png",
            }
            assert all(len(n.split("/")) == 2 for n in archive.namelist())
            for name in archive.namelist():
                assert name.endswith(".png")
                assert archive.read(name).startswith(bytes([137,80,78,71,13,10,26,10]))


def test_playlist_all_download_empty_returns_error_and_qr_ui_matches_video(configured_app):
    """Không có QR: trả lời rõ; nút Tạo video đã có QR tự ẩn."""
    app, keys, web = configured_app
    with app.test_client() as client:
        with client.session_transaction() as session:
            session["user_id"] = keys["teacher"]
        response = client.post("/playlists/qr/download-selected", data={
            "download_scope": "all_assigned"
        }, headers={"Accept": "application/json"})
        assert response.status_code == 409
        assert "Chưa có QR hợp lệ" in response.get_json()["message"]
    html = (ROOT / "templates/videos.html").read_text(encoding="utf-8")
    js = (ROOT / "static/research_measurement.js").read_text(encoding="utf-8")
    playlist_row = (ROOT / "templates/_playlist_library_row.html").read_text(encoding="utf-8")
    assert "create.hidden=hasQr;create.disabled=!select.value" in html
    assert "'hidden' if vqr.assigned_qr" in html
    assert "'hidden' if chosen_playlist_course.has_qr" in playlist_row
    assert "formnovalidate" in html
    assert "allPlaylistQrs=isPlaylistBulk(form)" in js
    assert "event.submitter?.formAction?.includes('/playlists/bulk-create-course-qrs')" in js




def test_qr_downloads_use_original_media_titles_without_browser_write_prompts(configured_app):
    """Tải PNG dùng Content-Disposition đúng tên, ZIP dùng trình duyệt native."""
    from urllib.parse import unquote
    from bs4 import BeautifulSoup
    from models import db, Course, CourseVideo, CoursePlaylist, QrCode
    app, keys, web = configured_app
    with app.app_context():
        teacher = db.session.get(web.User, keys["teacher"])
        course = db.session.get(Course, keys["course"])
        video = db.session.get(web.Video, keys["video_ids"][12])
        playlist = db.session.get(web.Playlist, keys["playlist"])
        video.title = "Tiếng Việt: Bài 4 / Lập trình"
        playlist.title = "Playlist: Học Python / Cơ bản"
        video_link, _ = web.ensure_course_video_link(course, video, teacher)
        qr_video, _ = web.create_qr_for_course_video(
            course, video, teacher, video_link
        )
        playlist_link, _ = web.ensure_course_playlist_link(
            course, playlist, teacher
        )
        qr_playlist, _ = web.create_qr_for_course_playlist(
            course, playlist, teacher, playlist_link
        )
        db.session.commit()
        video_id, playlist_id = qr_video.id, qr_playlist.id
    with app.test_client() as client:
        with client.session_transaction() as ss:
            ss["user_id"] = keys["teacher"]
        page = client.get("/videos")
        assert page.status_code == 200
        soup = BeautifulSoup(page.data, "html.parser")
        opt_video = soup.select_one(
            f"#video-{keys['video_ids'][12]} option[data-qr-png]"
        )
        opt_playlist = soup.select_one(
            f"#playlist-{keys['playlist']} option[data-qr-png]"
        )
        assert opt_video["data-qr-filename"] == "Tiếng Việt: Bài 4 / Lập trình.png"
        assert opt_playlist["data-qr-filename"] == "Playlist: Học Python / Cơ bản.png"
        assert not soup.select('script[src*="qr_save_picker.js"]')
        assert soup.select('script[src*="research_measurement.js?v=confirm-visible-20261126"]')
        for qr_id, expected in (
            (video_id, "Tiếng Việt_ Bài 4 _ Lập trình.png"),
            (playlist_id, "Playlist_ Học Python _ Cơ bản.png"),
        ):
            download = client.get(f"/qr/{qr_id}/png")
            assert download.status_code == 200
            assert download.mimetype == "image/png"
            assert download.data.startswith(bytes([137,80,78,71,13,10,26,10]))
            assert expected in unquote(download.headers["Content-Disposition"])

    ui = (ROOT / "templates/videos.html").read_text(encoding="utf-8")
    js = (ROOT / "static/research_measurement.js").read_text(encoding="utf-8")
    assert "download.download=(option.dataset.qrFilename" in ui
    assert "window.showDirectoryPicker(" not in js
    assert "window.showSaveFilePicker(" not in js
    assert "const a=document.createElement('a');" in js
    assert "a.download=allVideoQrs?" in js
    assert "await recordDownload(style,ids,'not_verified')" in js
    assert "queuePending(style,ids)" in js




def test_zip_folder_names_are_safe_unique_and_keep_vietnamese():
    """Trùng tên môn/QR vẫn không ghi đè; tên môn có dấu vẫn hiển thị."""
    from types import SimpleNamespace
    import app as web
    c1 = SimpleNamespace(id=17, name="Lập trình / Python")
    c2 = SimpleNamespace(id=18, name="Lập trình / Python")
    p = SimpleNamespace(title="Bài 01: Toán rời rạc")
    qr1 = SimpleNamespace(course=c1, is_playlist=True, playlist=p,
                          slug="first-qr", id=21, title="Unused")
    qr2 = SimpleNamespace(course=c1, is_playlist=True, playlist=p,
                          slug="second-qr", id=22, title="Unused")
    qr3 = SimpleNamespace(course=c2, is_playlist=True, playlist=p,
                          slug="third-qr", id=23, title="Unused")
    names = set()
    first = web.qr_zip_entry_name(qr1, names)
    second = web.qr_zip_entry_name(qr2, names)
    third = web.qr_zip_entry_name(qr3, names)
    assert len(names) == 3
    assert first == "Lập trình _ Python (MH000017)/Bài 01_ Toán rời rạc.png"
    assert second == "Lập trình _ Python (MH000017)/Bài 01_ Toán rời rạc_second-qr.png"
    assert third == "Lập trình _ Python (MH000018)/Bài 01_ Toán rời rạc.png"
    assert all(name.count("/") == 1 for name in names)
    # Phân loại chỉ thay đổi cách đóng gói ZIP, không thay đổi tên PNG tải riêng.
    assert web.qr_download_name(qr1) == "Bài 01_ Toán rời rạc.png"




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
