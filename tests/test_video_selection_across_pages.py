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
    assert 'window.videoBulkSelection?.hasAny()' in js
    assert 'chosenVideos' not in js
    assert 'filtered_library_video_query' in py
    assert 'selected_filtered_library_video_ids(user, request.form)' in py
    assert 'id="resetPlaylistFilters"' in template
    assert 'id="resetVideoFilters"' in template
    assert 'library_filter_reset.js' in template
    reset_js=(ROOT/"static/library_filter_reset.js").read_text(encoding="utf-8")
    assert 'slc-playlist-selection-v4:' in reset_js
    assert 'slc-video-selection-v1:' in reset_js
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
        assert q.count()==13, "Không được hiển thị video từ tài khoản khác"
        chosen=web.selected_filtered_library_video_ids(teacher,ImmutableMultiDict([
            ("q","Bài học"),("video_selection_mode","all"),
            ("excluded_video_ids",str(k["video_ids"][8])),
        ]))
        assert len(chosen)==12 and k["video_ids"][8] not in chosen
        none=web.selected_filtered_library_video_ids(teacher,ImmutableMultiDict([
            ("q","Bài học"),("video_selection_mode","none"),
            ("selected_video_ids",str(k["video_ids"][1])),
            ("selected_video_ids",str(k["video_ids"][11])),
            ("selected_video_ids",str(k["outsider"])),
        ]))
        assert set(none)=={k["video_ids"][1],k["video_ids"][11]}
        in_playlist=web.selected_filtered_library_video_ids(teacher,ImmutableMultiDict([
            ("q","Bài học"),("playlist_id",str(k["playlist"])),
            ("video_selection_mode","all"),
        ]))
        assert len(in_playlist)==4
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
        assert page2.data.count(b'class="form-check-input video-check"')==5
        assert page3.data.count(b'class="form-check-input video-check"')==3
        # Gán môn hàng loạt với tất cả 13 kết quả tìm kiếm, trừ 1 video ở TRANG 2.
        data={"course_id":str(k["course"]),"q":"Bài học",
              "video_selection_mode":"all",
              "excluded_video_ids":str(k["video_ids"][8])}
        response=client.post("/videos/assign-course",data=data)
        assert response.status_code==302
        with app.app_context():
            ids={link.video_id for link in CourseVideo.query.filter_by(course_id=k["course"]).all()}
            assert len(ids)==12 and k["video_ids"][8] not in ids
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
            assert len(qrs)==2
            assert all(q.owner_id==k["teacher"] for q in qrs)



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
        assert "Có 14 video" in vs.get_text(" ",strip=True)
        assert "Có 1 playlist" in ps.get_text(" ",strip=True)
