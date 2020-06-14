// License: Apache 2.0. See LICENSE file in root directory.
// Copyright(c) 2020 Intel Corporation. All Rights Reserved.
#include <functional>
#include <regex>
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


TEST_CASE("SW update test [version operators]")
{

    //////////////// Versions tests TEST START ///////////////////
    //  Tests the version structure operators                   //
    //////////////////////////////////////////////////////////////

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

//////////////// TEST 1 START ////////////////
// Download from corrupted format URL test  //
// Expect Download fail                     //
//////////////////////////////////////////////
TEST_CASE("SW update test [Download Error - corrupted URL]")
{
    versions_db_manager up_handler("Fake_URL...json");
    versions_db_manager::version ver;
    bool res(false);
    try {
        res = up_handler.query_versions("Intel RealSense L515", versions_db_manager::LIBREALSENSE, versions_db_manager::RECOMMENDED, ver);
    }
    catch (...)
    {
        REQUIRE(false);
    }
    REQUIRE_FALSE(res);
}


/////////// TEST 2 START /////////////
// Download from invalid URL test   //
// Expect Download fail             //
//////////////////////////////////////
TEST_CASE("SW update test [Download Error - invalid URL]")
{
    versions_db_manager up_handler("Fake_URL.json");
    versions_db_manager::version ver;
    bool res(false);
    try {
        res = up_handler.query_versions("Intel RealSense L515", versions_db_manager::LIBREALSENSE, versions_db_manager::RECOMMENDED, ver);
    }
    catch (...)
    {
        REQUIRE(false);
    }
    REQUIRE(false == res);
}



/////////////// TEST 3 START ///////////////////
// Download from s3 - not a version json      //
// Expect Download OK - Parse Fail            //
////////////////////////////////////////////////
TEST_CASE("SW update test [Download OK - Parse Fail]")
{
    versions_db_manager up_handler("http://realsense-hw-public.s3.amazonaws.com/rs-tests/post_processing_tests_2018_ww18/1551257880762.0.Input.csv");
    versions_db_manager::version ver;
    bool res(false);
    try {
        res = up_handler.query_versions("Intel RealSense L515", versions_db_manager::LIBREALSENSE, versions_db_manager::RECOMMENDED, ver);
    }
    catch (const std::exception& e)
    {
        REQUIRE(std::string(e.what()).substr(0, 11) == "parse error");
    }
    REQUIRE(false == res);
}
////////////////////////// TEST 4 START /////////////////////////
// Download a big file with a callback - not a valid json file //
// Expect Download OK - Parse Fail                             //
/////////////////////////////////////////////////////////////////
TEST_CASE("SW update test [Big file - Download OK - Parse Fail]")
{
    versions_db_manager up_handler("http://212.183.159.230/5MB.zip", false, mss_process_cb);
    versions_db_manager::version ver;
    bool res(false);
    try
    {
        res = up_handler.query_versions("Intel RealSense L515", versions_db_manager::LIBREALSENSE, versions_db_manager::RECOMMENDED, ver);
    }
    catch (const std::exception& e)
    {
        REQUIRE(std::string(e.what()).substr(0, 11) == "parse error");
    }
    REQUIRE(false == res);
}

////////////////////////// TEST 5 START /////////////////////////
// Download a big file with a callback - not a valid json file //
// Expect Download Fail                                        //
/////////////////////////////////////////////////////////////////
TEST_CASE("SW update test [Big file - Download Fail")
{
    versions_db_manager up_handler("http://212.183.159.230/5MB.zip", false, stop_process_cb);
    versions_db_manager::version ver;
    bool res(false);
    try
    {
        res = up_handler.query_versions("Intel RealSense L515", versions_db_manager::LIBREALSENSE, versions_db_manager::RECOMMENDED, ver);
    }
    catch (...)
    {
        REQUIRE(false);
    }
    REQUIRE(false == res);
}


////////////////////////// TEST 6 START ///////////////////////////////////////////
// Download a big file with a callback - with an empty callback function         //
// Expect Download OK - Parse Fail                                               //
///////////////////////////////////////////////////////////////////////////////////
TEST_CASE("SW update test [Empty callback")
{
    versions_db_manager up_handler("http://212.183.159.230/5MB.zip", false, empty_process_cb);
    versions_db_manager::version ver;
    bool res(false);
    try
    {
        res = up_handler.query_versions("Intel RealSense L515", versions_db_manager::LIBREALSENSE, versions_db_manager::RECOMMENDED, ver);
    }
    catch (const std::exception& e)
    {
        REQUIRE(std::string(e.what()).substr(0, 11) == "parse error");
    }
    REQUIRE(false == res);
}

////////////////////////// TEST 7 START ///////////////////
// Download valid json file from S3 json  - should work  //
// Expect - SUCCESS                                      //
///////////////////////////////////////////////////////////
TEST_CASE("SW update test [MSS Server file]")
{
    versions_db_manager up_handler("http://realsense-hw-public.s3-eu-west-1.amazonaws.com/rs-tests/sw-update/21_05_2020/rs_versions_db.json");
    versions_db_manager::version ver;
    bool res(false), ver_link_res(false), rel_notes_res(false), description_res(false);
    std::string ver_link, rel_notes, description;
    try
    {
        res = up_handler.query_versions("Intel RealSense L515", versions_db_manager::LIBREALSENSE, versions_db_manager::RECOMMENDED, ver);
        ver_link_res = up_handler.get_version_download_link(versions_db_manager::LIBREALSENSE, ver, ver_link);
        rel_notes_res = up_handler.get_version_release_notes(versions_db_manager::LIBREALSENSE, ver, rel_notes);
        description_res = up_handler.get_version_description(versions_db_manager::LIBREALSENSE, ver, description);
    }
    catch (...)
    {
        REQUIRE(false);
    }
    REQUIRE(res == true);
    REQUIRE(ver_link_res == true);
    REQUIRE(rel_notes_res == true);
    REQUIRE(description_res == true);
}

////////////////////////// TEST 8 START /////////////////
// Parse json local file                               //
// Expect Download OK - Parse OK                       //
/////////////////////////////////////////////////////////
TEST_CASE("SW update test [MSS local file]")
{
    versions_db_manager up_handler("rs_versions_db.json", true);
    versions_db_manager::version ver;
    bool res(false), ver_link_res(false), rel_notes_res(false), description_res(false);
    std::string ver_link, rel_notes, description;
    try
    {
        res = up_handler.query_versions("Intel RealSense L515", versions_db_manager::LIBREALSENSE, versions_db_manager::ESSENTIAL, ver);
        ver_link_res = up_handler.get_version_download_link(versions_db_manager::LIBREALSENSE, ver, ver_link);
        rel_notes_res = up_handler.get_version_release_notes(versions_db_manager::LIBREALSENSE, ver, rel_notes);
        description_res = up_handler.get_version_description(versions_db_manager::LIBREALSENSE, ver, description);
    }
    catch (...)
    {
        REQUIRE(false);
    }
    REQUIRE(res);
    REQUIRE(ver_link_res);
    REQUIRE(rel_notes_res);
    REQUIRE(description_res);
}

////////////////////////// TEST 9 START ///////////////////
// Parse json local file - Check Platform don't care '*' //
// Expect Download OK - Parse OK                         //
///////////////////////////////////////////////////////////
TEST_CASE("SW update test [MSS local file - Platform wildcard]")
{
    versions_db_manager up_handler("rs_versions_db.json", true);
    versions_db_manager::version ver;
    bool res(false), ver_link_res(false), rel_notes_res(false), description_res(false);
    std::string ver_link, rel_notes, description;
    try
    {
        res = up_handler.query_versions("Intel RealSense L515", versions_db_manager::LIBREALSENSE, versions_db_manager::RECOMMENDED, ver);
        ver_link_res = up_handler.get_version_download_link(versions_db_manager::LIBREALSENSE, 235000006, ver_link);
        rel_notes_res = up_handler.get_version_release_notes(versions_db_manager::LIBREALSENSE, 235000006, rel_notes);
        description_res = up_handler.get_version_description(versions_db_manager::LIBREALSENSE, 235000006, description);
    }
    catch (...)
    {
        REQUIRE(false);
    }
    REQUIRE(res);
    REQUIRE(ver_link_res);
    REQUIRE(rel_notes_res);
    REQUIRE(description_res);
    REQUIRE(ver == versions_db_manager::version("2.35.0.5"));
}

////////////////////////// TEST 10 START ///////////////////
// Download from s3 server to local file                  //
// Expect Download OK - Parse OK                          //
///////////////////////////////////////////////////////////
TEST_CASE("SW update test [MSS Download to file]")
{
    http_downloader downloader;
    downloader.download_to_file("http://realsense-hw-public.s3-eu-west-1.amazonaws.com/rs-tests/sw-update/21_05_2020/rs_versions_db.json", "file_test.txt");
    std::ifstream file_test("file_test.txt");
    REQUIRE(file_test.good());
}

