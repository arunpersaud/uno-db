/*
 * input.js --  this is part of a web interface for UNO-darmstadt
 *
 * Copyright 2013 Arun Persaud
 *
 * ------------------------------------------------------------------------
 *
 * UNO-darmstadt is free software: you can redistribute it and/or modify
 * it under the terms of the GNU General Public License as published by
 * the Free Software Foundation, either version 3 of the License, or (at
 * your option) any later version.
 *
 * UNO-darmstadt is distributed in the hope that it will be useful, but
 * WITHOUT ANY WARRANTY; without even the implied warranty of
 * MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the GNU
 * General Public License for more details.
 *
 * You should have received a copy of the GNU General Public License
 * along with this program. If not, see http://www.gnu.org/licenses/.  *
 *
 * ------------------------------------------------------------------------
 *
 *  wep-page:
 *     http://uno-darmstadt.sourceforge.net
 *
 *  It would be nice to get some feedback (bugs or other comments), so please drop
 *  me a line if you are using UNO-darmstadt :)
 *  have fun
 *        Arun
 */

$(".game form").submit(function(event) {

    /* stop form from submitting normally */
    event.preventDefault();

    $.post("data-input.php",$(".game form").serialize(),
           function(data){ $('ul').before("<p>"+data+"</p>").prev().css('background-color','red').fadeOut(10000) },
           'html');

  });

/* update numeric input names */
 function updateinput() {
   $('input[type="number"]').each(function(i) { $(this).removeAttr("name"); });
   $('input[type="number"]').each(function(i) { $(this).attr("name",i ); });
 }

/* adds a column to a game table */
function addCol() {
    var currentNumberOfTDsInARow = $('.game table tr:last td').length;
    newColNum = currentNumberOfTDsInARow;
    var rows = $('.game tbody tr');
    $('.game thead tr').find('th:last').html(printselectplayer(newColNum)); /* defined in data-input.php */
    $('.game thead tr').find('th:last').after('<th><button class="newplayer">new player</button></th>');
    for (var i = 0; i < rows.length; i++) {
        $(rows[i]).find('td:last').before('<td><input type="text" name="game-'+i+'-'+(newColNum-2)+'"></td>');
    }
    $(".newplayer").click(addCol);
    updateinput();
}
$(".newplayer").click(addCol);

/* adds a row to a game table */
function addRow() {
  var currentNumberOfRows = $('.game table tr').length -1;
  $('.game tbody tr').find('td:last').html('');
  var row = "<tr><td><input type=\"checkbox\" name=\"ewbc"+$('.game tbody tr').length+"\" value=\"ewbc\" /></td>";
  $('.game tbody tr:last').find('td:not(:first-child, :last-child)').each( function(index) {
      row = row.concat("<td><input type=\"text\" name=\"game-"+currentNumberOfRows+"-"+index+"\"></td> ") } );
  row=row.concat("<td><button class=\"newgame\">new row</button></td></tr>\n");

  $('.game tbody:last').append(row);
  $(".newgame").click(addRow);
  updateinput();
}
$(".newgame").click(addRow);

function tableedit() {
    mynewbutton = '<button class="save">save</button><button class="cancel">cancel</button>';
    myoldbutton = '<button class="edit">edit</button>';

    var table = $(this).parent().parent()

    var mycont= new Array();

    /* remember current content */
    table.find("td").each( function(index) { mycont[index]=$(this).html(); } );

    /* replace with input elements, skip first and last */
    table.find('td:not(:first-child, :last-child)').each( function(index) { $(this).html('<input type="text" value="'+ mycont[index+1] +'">')} )

    table.find("td:last-child").html(mynewbutton);
    $(".edit").attr("disabled", "disabled");

    /* add functions to exit edit */
    table.find("td:last-child").find(".cancel").click(function () {

    var table = $(this).parent().parent();

    table.find('td:not(:first-child, :last-child)').each( function(index) { $(this).html(mycont[index+1])} );
    $(".edit").removeAttr("disabled");
    table.find("td:last-child").html(mycont[mycont.length-1]).find(".edit").click(tableedit);

    });
    table.find("td:last-child").find(".save").click(function () {

       var table = $(this).parent().parent();

       var myclass = $(this).closest("li").attr('class');
       var mydata = {};
       var datanew = {};

       /* update content */
       table.find("td input").each( function(index) { datanew[index]=$(this).attr("value"); } );

       var i,j=0;
       mydata.what  = myclass;
       mydata.token = token; /* defined in data-input.php */
       mydata.id    = mycont[0];
       j=2;
       for(i in mycont)
	 {mydata[j]=datanew[i];j++;}

       $.post("data-input.php",mydata,
              function(data){ $('ul').before("<p>"+data+"</p>").prev().css('background-color','red').fadeOut(10000) },
              'html');

       /* reset to new values */
       table.find('td:not(:first-child, :last-child)').each( function(index) { $(this).html(datanew[index])} );
       $(".edit").removeAttr("disabled");
       table.find("td:last-child").html(myoldbutton);

       /* if no id, add new row */
       var row = "<tr>";
       table.find('td:not(:last-child)').each( function(index) { row = row.concat("<td></td> ") } );
       row=row.concat("<td><button class=\"edit\">new</button></td></tr>");
       if(mycont[0].length===0)
	 {
	   table.closest('table').find('tbody:last').append(row);
	 }
       $(".edit").click(tableedit);

    });

}

$(".toggle").click(function ()     {   $(this).parent().find("table").toggle(); });
$(".gametoggle").click(function () {   $(this).parent().find("form").toggle(); });
$(".edit").click(tableedit);

