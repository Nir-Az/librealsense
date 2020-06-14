// License: Apache 2.0. See LICENSE file in root directory.
// Copyright(c) 2020 Intel Corporation. All Rights Reserved.
#include "sw-update-common.h"
#include "versions-db-manager.h"


using namespace rs2::http;
using namespace rs2::sw_update;



////////////////////////////
// Set callback functions //
////////////////////////////

// Main success scenario callback (Continue download)
std::function<callback_result(uint64_t dl_current_bytes, uint64_t dl_total_bytes)> mss_process_cb =
[](uint64_t dl_current_bytes, uint64_t dl_total_bytes) -> callback_result {
    std::cout << "DOWN:" << dl_current_bytes << " of " << dl_total_bytes << std::endl;
    return callback_result::CONTINUE_DOWNLOAD;
};

// Stop download callback scenario 
std::function<callback_result(uint64_t dl_current_bytes, uint64_t dl_total_bytes)> stop_process_cb =
[](uint64_t dl_current_bytes, uint64_t dl_total_bytes) -> callback_result {
    std::cout << "DOWN:" << dl_current_bytes << " of " << dl_total_bytes << std::endl;
    return callback_result::STOP_DOWNLOAD;
};

// Empty callback scenario 
std::function<callback_result(uint64_t dl_current_bytes, uint64_t dl_total_bytes)> empty_process_cb;

//////////////////////// TEST Description ////////////////////
//  Tests the version structure operators                   //
//////////////////////////////////////////////////////////////
TEST_CASE("SW update test [version operator >]")
{

    /////////////////////// Test operator >  /////////////////////
    // Verify success
    REQUIRE(versions_db_manager::version("1.2.3.4") > versions_db_manager::version("0.2.3.4"));
    REQUIRE(versions_db_manager::version("1.2.3.4") > versions_db_manager::version("1.1.3.4"));
    REQUIRE(versions_db_manager::version("1.2.3.4") > versions_db_manager::version("1.2.2.4"));
    REQUIRE(versions_db_manager::version("1.2.3.4") > versions_db_manager::version("1.2.3.3"));

    // Verify failure
    REQUIRE(false == (versions_db_manager::version("1.2.3.4") > versions_db_manager::version("2.2.3.4")));
    REQUIRE(false == (versions_db_manager::version("1.2.3.4") > versions_db_manager::version("1.3.3.4")));
    REQUIRE(false == (versions_db_manager::version("1.2.3.4") > versions_db_manager::version("1.2.4.4")));
    REQUIRE(false == (versions_db_manager::version("1.2.3.4") > versions_db_manager::version("1.2.3.5")));
    REQUIRE(false == (versions_db_manager::version("1.2.3.4") > versions_db_manager::version("1.2.3.4")));

    /////////////////////// Test operator <  /////////////////////
    // Verify success
    REQUIRE(versions_db_manager::version("1.2.3.4") < versions_db_manager::version("2.2.3.4"));
    REQUIRE(versions_db_manager::version("1.2.3.4") < versions_db_manager::version("1.3.3.4"));
    REQUIRE(versions_db_manager::version("1.2.3.4") < versions_db_manager::version("1.2.4.4"));
    REQUIRE(versions_db_manager::version("1.2.3.4") < versions_db_manager::version("1.2.3.5"));

    // Verify failure
    REQUIRE(false == (versions_db_manager::version("1.2.3.4") < versions_db_manager::version("0.2.3.4")));
    REQUIRE(false == (versions_db_manager::version("1.2.3.4") < versions_db_manager::version("1.1.3.4")));
    REQUIRE(false == (versions_db_manager::version("1.2.3.4") < versions_db_manager::version("1.2.2.4")));
    REQUIRE(false == (versions_db_manager::version("1.2.3.4") < versions_db_manager::version("1.2.3.3")));

    REQUIRE(false == (versions_db_manager::version("1.2.3.4") < versions_db_manager::version("1.2.3.4")));

    /////////////////////// Test operator ==  /////////////////////
    // Verify success
    REQUIRE(versions_db_manager::version("1.2.3.4") == versions_db_manager::version("1.2.3.4"));
    REQUIRE(versions_db_manager::version("0.0.0.10") == versions_db_manager::version("0.0.0.10"));

    // Verify failure
    REQUIRE(false == (versions_db_manager::version("1.2.3.4") == versions_db_manager::version("0.2.3.4")));
    REQUIRE(false == (versions_db_manager::version("1.2.3.4") == versions_db_manager::version("1.1.3.4")));
    REQUIRE(false == (versions_db_manager::version("1.2.3.4") == versions_db_manager::version("1.2.2.4")));
    REQUIRE(false == (versions_db_manager::version("1.2.3.4") == versions_db_manager::version("1.2.3.3")));

    /////////////////////// Test operator !=  /////////////////////
    // Verify success
    REQUIRE(versions_db_manager::version("1.2.3.4") != versions_db_manager::version("0.2.3.4"));
    REQUIRE(versions_db_manager::version("1.2.3.4") != versions_db_manager::version("1.1.3.4"));
    REQUIRE(versions_db_manager::version("1.2.3.4") != versions_db_manager::version("1.2.2.4"));
    REQUIRE(versions_db_manager::version("1.2.3.4") != versions_db_manager::version("1.2.3.3"));

    // Verify failure
    REQUIRE(false == (versions_db_manager::version("1.2.3.4") != versions_db_manager::version("1.2.3.4")));
    REQUIRE(false == (versions_db_manager::version("0.0.0.10") != versions_db_manager::version("0.0.0.10")));

    /////////////////////// Test operator >=  /////////////////////
    // Verify success
    REQUIRE(versions_db_manager::version("1.2.3.4") >= versions_db_manager::version("1.2.3.4"));

    REQUIRE(versions_db_manager::version("2.2.3.4") >= versions_db_manager::version("1.2.3.4"));
    REQUIRE(versions_db_manager::version("1.3.3.4") >= versions_db_manager::version("1.2.3.4"));
    REQUIRE(versions_db_manager::version("1.2.4.4") >= versions_db_manager::version("1.2.3.4"));
    REQUIRE(versions_db_manager::version("1.2.3.5") >= versions_db_manager::version("1.2.3.4"));

    // Verify failure
    REQUIRE(false == (versions_db_manager::version("1.2.3.4") >= versions_db_manager::version("2.2.3.4")));
    REQUIRE(false == (versions_db_manager::version("1.2.3.4") >= versions_db_manager::version("1.3.3.4")));
    REQUIRE(false == (versions_db_manager::version("1.2.3.4") >= versions_db_manager::version("1.2.4.4")));
    REQUIRE(false == (versions_db_manager::version("1.2.3.4") >= versions_db_manager::version("1.2.3.5")));

    /////////////////////// Test operator <=  /////////////////////
    // Verify success
    REQUIRE(versions_db_manager::version("1.2.3.4") <= versions_db_manager::version("1.2.3.4"));

    REQUIRE(versions_db_manager::version("1.2.3.4") <= versions_db_manager::version("2.2.3.4"));
    REQUIRE(versions_db_manager::version("1.2.3.4") <= versions_db_manager::version("1.3.3.4"));
    REQUIRE(versions_db_manager::version("1.2.3.4") <= versions_db_manager::version("1.2.4.4"));
    REQUIRE(versions_db_manager::version("1.2.3.4") <= versions_db_manager::version("1.2.3.5"));

    // Verify failure
    REQUIRE(false == (versions_db_manager::version("2.2.3.4") <= versions_db_manager::version("1.2.3.4")));
    REQUIRE(false == (versions_db_manager::version("1.3.3.4") <= versions_db_manager::version("1.2.3.4")));
    REQUIRE(false == (versions_db_manager::version("1.2.4.4") <= versions_db_manager::version("1.2.3.4")));
    REQUIRE(false == (versions_db_manager::version("1.2.3.5") <= versions_db_manager::version("1.2.3.4")));

}

//////////////// TEST Description ////////////
// http downloader test                     //
// Download from corrupted format URL test  //
// Expect Download fail                     //
//////////////////////////////////////////////
TEST_CASE("SW update http_downloader test [Download Error - corrupted URL]")
{
    rs2::log_to_console(RS2_LOG_SEVERITY_WARN);
    http_downloader downloader;
    std::vector <uint8_t> vec;
    REQUIRE_FALSE(downloader.download_to_bytes_vector("Fake_URL...json", vec));
}

//////////////// TEST Description ////////////
// http downloader test                     //
// Download from invalid URL test           //
// Expect Download fail                     //
//////////////////////////////////////////////
TEST_CASE("SW update http_downloader test [Download Error - invalid URL]")
{
    rs2::log_to_console(RS2_LOG_SEVERITY_WARN);
    http_downloader downloader;
    std::vector <uint8_t> vec;
    REQUIRE_FALSE(downloader.download_to_bytes_vector("Fake_URL.json", vec));
}

//////////////////////// TEST Description //////////////////
// http downloader test                                   //
// Download from s3 server to vector                      //
// Expect Download OK - Parse OK                          //
///////////////////////////////////////////////////////////
TEST_CASE("SW update http_downloader test [MSS Download to vector]")
{
    http_downloader downloader;
    std::vector <uint8_t> vec;
    downloader.download_to_bytes_vector("http://realsense-hw-public.s3-eu-west-1.amazonaws.com/rs-tests/sw-update/21_05_2020/rs_versions_db.json", vec);
    REQUIRE(vec.size() > 0);
}

//////////////////////// TEST Description //////////////////
// http downloader test                                   //
// Download from s3 server to stringstream                //
// Expect Download OK - Parse OK                          //
///////////////////////////////////////////////////////////
TEST_CASE("SW update http_downloader test [MSS Download to stringstream]")
{
    http_downloader downloader;
    std::stringstream ss;
    downloader.download_to_stream("http://realsense-hw-public.s3-eu-west-1.amazonaws.com/rs-tests/sw-update/21_05_2020/rs_versions_db.json", ss);
    REQUIRE(ss.good());
}

//////////////////////// TEST Description //////////////////
// http downloader test                                   //
// Download from s3 server to local file                  //
// Expect Download OK - Parse OK                          //
///////////////////////////////////////////////////////////
TEST_CASE("SW update http_downloader test [MSS Download to file]")
{
    http_downloader downloader;
    downloader.download_to_file("http://realsense-hw-public.s3-eu-west-1.amazonaws.com/rs-tests/sw-update/21_05_2020/rs_versions_db.json", "file_test.txt");
    std::ifstream file_test("file_test.txt");
    REQUIRE(file_test.good());
}

//////////////////////// TEST Description ///////////////////////
// http downloader test                                        //
// Download a big file with a callback - not a valid json file //
// Expect Download Fail                                        //
/////////////////////////////////////////////////////////////////
TEST_CASE("SW update http_downloader test [Big file - Download Fail")
{
    http_downloader downloader;
    std::vector <uint8_t> success_vec;
    std::vector <uint8_t> fail_vec;
    auto success_res = downloader.download_to_bytes_vector("http://212.183.159.230/5MB.zip", success_vec, mss_process_cb);
    auto fail_res = downloader.download_to_bytes_vector("http://212.183.159.230/5MB.zip", fail_vec, stop_process_cb);
    REQUIRE(success_vec.size() > fail_vec.size());
    REQUIRE(success_res);
    REQUIRE_FALSE(fail_res);
}

/////////////////////////////////// TEST Description //////////////////////////////
// http downloader test                                                          //
// Download a big file with a callback - with an empty callback function         //
// Expect Download OK                                                            //
///////////////////////////////////////////////////////////////////////////////////
TEST_CASE("SW update http_downloader test [Empty callback")
{
    http_downloader downloader;
    std::vector <uint8_t> vec;
    auto success_res = downloader.download_to_bytes_vector("http://212.183.159.230/5MB.zip", vec, empty_process_cb);
    REQUIRE(vec.size() > 0);
    REQUIRE(success_res);
}

//////////////// TEST Description ////////////
// versions-db-manager test                 //
// Download from corrupted format URL test  //
// Expect Download fail                     //
//////////////////////////////////////////////
TEST_CASE("SW update test [Download Error - corrupted URL]")
{
    versions_db_manager up_handler("Fake_URL...json");
    versions_db_manager::version ver;
    bool res(false);

    REQUIRE_NOTHROW(res = up_handler.query_versions("Intel RealSense L515", versions_db_manager::LIBREALSENSE, versions_db_manager::RECOMMENDED, ver));
    REQUIRE_FALSE(res);
}

///////////// TEST Description ///////
// versions-db-manager test         //
// Download from invalid URL test   //
// Expect Download fail             //
//////////////////////////////////////
TEST_CASE("SW update test [Download Error - invalid URL]")
{
    versions_db_manager up_handler("Fake_URL.json");
    versions_db_manager::version ver;
    bool res(false);

    REQUIRE_NOTHROW(res = up_handler.query_versions("Intel RealSense L515", versions_db_manager::LIBREALSENSE, versions_db_manager::RECOMMENDED, ver));
    REQUIRE_FALSE(res);
}

//////////////// TEST Description //////////////
// versions-db-manager test                   //
// Download from s3 - not a version json      //
// Expect Download OK - Parse Fail            //
////////////////////////////////////////////////
TEST_CASE("SW update test [Download OK - Parse Fail]")
{
    versions_db_manager up_handler("http://realsense-hw-public.s3.amazonaws.com/rs-tests/post_processing_tests_2018_ww18/1551257880762.0.Input.csv");
    versions_db_manager::version ver;
    bool res(false);

    REQUIRE_THROWS(res = up_handler.query_versions("Intel RealSense L515", versions_db_manager::LIBREALSENSE, versions_db_manager::RECOMMENDED, ver));
    REQUIRE_FALSE(res);
}
///////////////////// TEST Description //////////////////////////
// versions-db-manager test                                    //
// Download a big file with a callback - not a valid json file //
// Expect Download OK - Parse Fail                             //
/////////////////////////////////////////////////////////////////
TEST_CASE("SW update test [Big file - Download OK - Parse Fail]")
{
    versions_db_manager up_handler("http://212.183.159.230/5MB.zip", false, mss_process_cb);
    versions_db_manager::version ver;
    bool res(false);

    REQUIRE_THROWS(res = up_handler.query_versions("Intel RealSense L515", versions_db_manager::LIBREALSENSE, versions_db_manager::RECOMMENDED, ver));
    REQUIRE_FALSE(res);
}

//////////////////////// TEST Description ///////////////////////
// versions-db-manager test                                    //
// Download a big file with a callback - not a valid json file //
// Expect Download Fail                                        //
/////////////////////////////////////////////////////////////////
TEST_CASE("SW update test [Big file - Download Fail")
{
    versions_db_manager up_handler("http://212.183.159.230/5MB.zip", false, stop_process_cb);
    versions_db_manager::version ver;
    bool res(false);
    REQUIRE_NOTHROW(res = up_handler.query_versions("Intel RealSense L515", versions_db_manager::LIBREALSENSE, versions_db_manager::RECOMMENDED, ver));
    REQUIRE_FALSE(res);
}


/////////////////////////////////// TEST Description //////////////////////////////
// versions-db-manager test                                                      //
// Download a big file with a callback - with an empty callback function         //
// Expect Download OK - Parse Fail                                               //
///////////////////////////////////////////////////////////////////////////////////
TEST_CASE("SW update test [Empty callback")
{
    versions_db_manager up_handler("http://212.183.159.230/5MB.zip", false, empty_process_cb);
    versions_db_manager::version ver;
    bool res(false);

    REQUIRE_THROWS(res = up_handler.query_versions("Intel RealSense L515", versions_db_manager::LIBREALSENSE, versions_db_manager::RECOMMENDED, ver));
    REQUIRE_FALSE(res);
}

//////////////////////// TEST Description /////////////////
// versions-db-manager test                              //
// Download valid json file from S3 json  - should work  //
// Expect - SUCCESS                                      //
///////////////////////////////////////////////////////////
TEST_CASE("SW update test [MSS Server file]")
{
    versions_db_manager up_handler("http://realsense-hw-public.s3-eu-west-1.amazonaws.com/rs-tests/sw-update/21_05_2020/rs_versions_db.json");
    versions_db_manager::version ver;
    bool res(false), ver_link_res(false), rel_notes_res(false), description_res(false);
    std::string ver_link, rel_notes, description;
    REQUIRE_NOTHROW(res = up_handler.query_versions("Intel RealSense L515", versions_db_manager::LIBREALSENSE, versions_db_manager::RECOMMENDED, ver));
    REQUIRE_NOTHROW(ver_link_res = up_handler.get_version_download_link(versions_db_manager::LIBREALSENSE, ver, ver_link));
    REQUIRE_NOTHROW(rel_notes_res = up_handler.get_version_release_notes(versions_db_manager::LIBREALSENSE, ver, rel_notes));
    REQUIRE_NOTHROW(description_res = up_handler.get_version_description(versions_db_manager::LIBREALSENSE, ver, description));
    REQUIRE(res == true);
    REQUIRE(ver_link_res == true);
    REQUIRE(rel_notes_res == true);
    REQUIRE(description_res == true);
}

////////////////////// TEST Description /////////////////
// versions-db-manager test                            //
// Parse json local file                               //
// Expect Download OK - Parse OK                       //
/////////////////////////////////////////////////////////
TEST_CASE("SW update test [MSS local file]")
{
    versions_db_manager up_handler("rs_versions_db.json", true);
    versions_db_manager::version ver;
    bool res(false), ver_link_res(false), rel_notes_res(false), description_res(false);
    std::string ver_link, rel_notes, description;

    REQUIRE_NOTHROW(res = up_handler.query_versions("Intel RealSense L515", versions_db_manager::LIBREALSENSE, versions_db_manager::ESSENTIAL, ver));
    REQUIRE_NOTHROW(ver_link_res = up_handler.get_version_download_link(versions_db_manager::LIBREALSENSE, ver, ver_link));
    REQUIRE_NOTHROW(rel_notes_res = up_handler.get_version_release_notes(versions_db_manager::LIBREALSENSE, ver, rel_notes));
    REQUIRE_NOTHROW(description_res = up_handler.get_version_description(versions_db_manager::LIBREALSENSE, ver, description));
    REQUIRE(res);
    REQUIRE(ver_link_res);
    REQUIRE(rel_notes_res);
    REQUIRE(description_res);
}

////////////////////// TEST Description ///////////////////
// versions-db-manager test                              //
// Parse json local file - Check Platform don't care '*' //
// Expect Download OK - Parse OK                         //
///////////////////////////////////////////////////////////
TEST_CASE("SW update test [MSS local file - Platform wildcard]")
{
    versions_db_manager up_handler("rs_versions_db.json", true);
    versions_db_manager::version ver;
    bool res(false), ver_link_res(false), rel_notes_res(false), description_res(false);
    std::string ver_link, rel_notes, description;
    REQUIRE_NOTHROW(res = up_handler.query_versions("Intel RealSense L515", versions_db_manager::LIBREALSENSE, versions_db_manager::RECOMMENDED, ver));
    REQUIRE_NOTHROW(ver_link_res = up_handler.get_version_download_link(versions_db_manager::LIBREALSENSE, 235000006, ver_link));
    REQUIRE_NOTHROW(rel_notes_res = up_handler.get_version_release_notes(versions_db_manager::LIBREALSENSE, 235000006, rel_notes));
    REQUIRE_NOTHROW(description_res = up_handler.get_version_description(versions_db_manager::LIBREALSENSE, 235000006, description));
    REQUIRE(res);
    REQUIRE(ver_link_res);
    REQUIRE(rel_notes_res);
    REQUIRE(description_res);
    REQUIRE(ver == versions_db_manager::version("2.35.0.5"));
}



